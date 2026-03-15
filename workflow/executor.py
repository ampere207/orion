from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import networkx as nx

from agent_registry.registry import AgentRegistry
from agents.agent_messaging import AgentMessaging
from agents.agent_router import AgentRouter
from memory.context_manager import ContextManager
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from workflow.retry_manager import RetryManager
from workflow.workflow_state import WorkflowState, WorkflowStateTracker


class WorkflowExecutor:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
        state_tracker: WorkflowStateTracker,
        context_manager: ContextManager,
        messaging: AgentMessaging,
        agent_router: AgentRouter,
        retry_manager: RetryManager,
    ) -> None:
        self._agent_registry = agent_registry
        self._short_term_memory = short_term_memory
        self._long_term_memory = long_term_memory
        self._state_tracker = state_tracker
        self._context_manager = context_manager
        self._messaging = messaging
        self._agent_router = agent_router
        self._retry_manager = retry_manager

    async def execute(
        self,
        workflow_id: str,
        user_task: str,
        graph: nx.DiGraph,
        initial_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._state_tracker.update(workflow_id, WorkflowState.RUNNING)
        await self._long_term_memory.save_workflow_history(workflow_id, WorkflowState.RUNNING.value, user_task)
        await self._context_manager.update_context(workflow_id, initial_context or {})
        await self._append_event(workflow_id, "workflow_started", {"task": user_task})

        node_outputs: dict[str, dict[str, Any]] = {}
        completed: set[str] = set()
        in_progress: set[str] = set()

        for node_id in nx.topological_sort(graph):
            node_data = graph.nodes[node_id]
            self._state_tracker.record_step(
                workflow_id,
                node_id,
                {
                    "node_id": node_id,
                    "agent": node_data.get("agent"),
                    "task": node_data.get("task"),
                    "tool": node_data.get("tool"),
                    "depends_on": list(graph.predecessors(node_id)),
                    "status": WorkflowState.PENDING.value,
                    "attempts": 0,
                },
            )

        try:
            while len(completed) < graph.number_of_nodes():
                ready_nodes = [
                    node
                    for node in graph.nodes
                    if node not in completed
                    and node not in in_progress
                    and all(pred in completed for pred in graph.predecessors(node))
                ]

                if not ready_nodes:
                    raise RuntimeError("Deadlock detected while executing workflow graph")

                tasks = [
                    asyncio.create_task(
                        self._run_node_with_retry(
                            workflow_id=workflow_id,
                            node_id=node_id,
                            graph=graph,
                            user_task=user_task,
                            node_outputs=node_outputs,
                            initial_context=initial_context or {},
                        )
                    )
                    for node_id in ready_nodes
                ]
                in_progress.update(ready_nodes)

                results = await asyncio.gather(*tasks)
                for node_id, output, attempts in results:
                    node_outputs[node_id] = output
                    completed.add(node_id)
                    in_progress.discard(node_id)
                    self._state_tracker.record_step(
                        workflow_id,
                        node_id,
                        {
                            "status": WorkflowState.COMPLETED.value,
                            "attempts": attempts,
                            "output": output,
                        },
                    )

            ordered_nodes = list(nx.topological_sort(graph))
            final_output = node_outputs.get(ordered_nodes[-1], {"output": ""})
            timeline = await self._context_manager.get_progress(workflow_id)
            shared_context = await self._context_manager.get_context(workflow_id)

            self._state_tracker.update(
                workflow_id,
                WorkflowState.COMPLETED,
                details={"result": final_output.get("output", "")},
            )
            await self._append_event(workflow_id, "workflow_completed", {"result": final_output.get("output", "")})
            await self._long_term_memory.save_workflow_history(
                workflow_id,
                WorkflowState.COMPLETED.value,
                user_task,
                result=str(final_output.get("output", "")),
            )
            return {
                "workflow_id": workflow_id,
                "status": WorkflowState.COMPLETED.value,
                "result": final_output.get("output", ""),
                "steps": list(self._state_tracker.get(workflow_id).steps.values()),
                "node_outputs": node_outputs,
                "timeline": timeline,
                "shared_context": shared_context,
            }
        except Exception as exc:
            self._state_tracker.update(workflow_id, WorkflowState.FAILED, details={"error": str(exc)})
            await self._append_event(workflow_id, "workflow_failed", {"error": str(exc)})
            await self._long_term_memory.save_workflow_history(
                workflow_id,
                WorkflowState.FAILED.value,
                user_task,
                error=str(exc),
            )
            raise

    async def _run_node_with_retry(
        self,
        workflow_id: str,
        node_id: str,
        graph: nx.DiGraph,
        user_task: str,
        node_outputs: dict[str, dict[str, Any]],
        initial_context: dict[str, Any],
    ) -> tuple[str, dict[str, Any], int]:
        await self._append_event(workflow_id, "step_started", {"node_id": node_id})
        self._state_tracker.record_step(workflow_id, node_id, {"status": WorkflowState.RUNNING.value})

        async def operation() -> tuple[str, dict[str, Any]]:
            return await self._run_node(
                workflow_id=workflow_id,
                node_id=node_id,
                graph=graph,
                user_task=user_task,
                node_outputs=node_outputs,
                initial_context=initial_context,
            )

        try:
            result, attempts = await self._retry_manager.run(operation)
            await self._append_event(workflow_id, "step_completed", {"node_id": node_id, "attempts": attempts})
            return result[0], result[1], attempts
        except Exception as exc:
            self._state_tracker.record_step(
                workflow_id,
                node_id,
                {
                    "status": WorkflowState.FAILED.value,
                    "attempts": self._retry_manager.max_retries,
                    "error": str(exc),
                },
            )
            await self._append_event(
                workflow_id,
                "step_failed",
                {"node_id": node_id, "attempts": self._retry_manager.max_retries, "error": str(exc)},
            )
            raise

    async def _run_node(
        self,
        workflow_id: str,
        node_id: str,
        graph: nx.DiGraph,
        user_task: str,
        node_outputs: dict[str, dict[str, Any]],
        initial_context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        node_data = graph.nodes[node_id]
        agent_name = node_data.get("agent") or await self._agent_router.route(node_data.get("task") or user_task)
        task = node_data.get("task") or user_task

        agent = self._agent_registry.get_agent(agent_name)
        successor_agents = []
        for successor in graph.successors(node_id):
            successor_data = graph.nodes[successor]
            successor_agents.append(
                successor_data.get("agent") or await self._agent_router.route(successor_data.get("task") or user_task)
            )

        predecessor_outputs = {
            predecessor: node_outputs.get(predecessor) for predecessor in graph.predecessors(node_id)
        }
        context = {
            **initial_context,
            "workflow_id": workflow_id,
            "node_id": node_id,
            "predecessor_outputs": predecessor_outputs,
            "tool": node_data.get("tool"),
            "successor_agents": successor_agents,
        }

        output = await agent.execute(task, context)
        await self._short_term_memory.set_node_output(workflow_id, node_id, output)
        await self._context_manager.update_context(workflow_id, {f"{node_id}_result": output})
        return node_id, output

    async def _append_event(self, workflow_id: str, event_type: str, details: dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **details,
        }
        self._state_tracker.append_timeline(workflow_id, event)
        await self._context_manager.append_progress(workflow_id, event)
