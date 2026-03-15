from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import networkx as nx

from agent_registry.registry import AgentRegistry
from agents.agent_router import AgentRouter
from core.config import Settings
from memory.context_manager import ContextManager
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from messaging.rabbitmq_client import RabbitMQClient
from runtime.concurrency_manager import ConcurrencyManager
from runtime.task_dispatcher import TaskDispatcher
from workers.worker_manager import WorkerManager
from workflow.retry_manager import RetryManager
from workflow.workflow_state import WorkflowState, WorkflowStateTracker


class WorkflowExecutor:
    def __init__(
        self,
        settings: Settings,
        agent_registry: AgentRegistry,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
        state_tracker: WorkflowStateTracker,
        context_manager: ContextManager,
        agent_router: AgentRouter,
        retry_manager: RetryManager,
        task_dispatcher: TaskDispatcher,
        concurrency_manager: ConcurrencyManager,
        worker_manager: WorkerManager,
        rabbitmq_client: RabbitMQClient,
    ) -> None:
        self._settings = settings
        self._agent_registry = agent_registry
        self._short_term_memory = short_term_memory
        self._long_term_memory = long_term_memory
        self._state_tracker = state_tracker
        self._context_manager = context_manager
        self._agent_router = agent_router
        self._retry_manager = retry_manager
        self._task_dispatcher = task_dispatcher
        self._concurrency_manager = concurrency_manager
        self._worker_manager = worker_manager
        self._rabbitmq_client = rabbitmq_client

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
            step_agent = node_data.get("agent") or await self._agent_router.route(node_data.get("task") or user_task)
            step_task = node_data.get("task") or user_task
            step_tool = node_data.get("tool")
            step_depends = list(graph.predecessors(node_id))

            step_payload = {
                "node_id": node_id,
                "agent": step_agent,
                "task": step_task,
                "tool": step_tool,
                "depends_on": step_depends,
                "status": WorkflowState.PENDING.value,
                "attempts": 0,
            }
            self._state_tracker.record_step(workflow_id, node_id, step_payload)
            await self._long_term_memory.save_workflow_step(
                workflow_id=workflow_id,
                node_id=node_id,
                agent=step_agent,
                task=step_task,
                status=WorkflowState.PENDING.value,
                attempts=0,
                tool=step_tool,
                depends_on=step_depends,
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
                        self._concurrency_manager.run(
                            self._run_node_with_retry(
                                workflow_id=workflow_id,
                                node_id=node_id,
                                graph=graph,
                                user_task=user_task,
                                node_outputs=node_outputs,
                                initial_context=initial_context or {},
                            )
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
                    step = self._state_tracker.get(workflow_id).steps[node_id]
                    await self._long_term_memory.save_workflow_step(
                        workflow_id=workflow_id,
                        node_id=node_id,
                        agent=step.get("agent") or "unknown",
                        task=step.get("task") or user_task,
                        status=WorkflowState.COMPLETED.value,
                        attempts=attempts,
                        tool=step.get("tool"),
                        depends_on=step.get("depends_on", []),
                        output=output,
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
            return await self._dispatch_and_wait_node(
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
            step = self._state_tracker.get(workflow_id).steps.get(node_id, {})
            self._state_tracker.record_step(
                workflow_id,
                node_id,
                {
                    "status": WorkflowState.FAILED.value,
                    "attempts": self._retry_manager.max_retries,
                    "error": str(exc),
                },
            )
            await self._long_term_memory.save_workflow_step(
                workflow_id=workflow_id,
                node_id=node_id,
                agent=step.get("agent") or "unknown",
                task=step.get("task") or user_task,
                status=WorkflowState.FAILED.value,
                attempts=self._retry_manager.max_retries,
                tool=step.get("tool"),
                depends_on=step.get("depends_on", []),
                error=str(exc),
            )
            await self._append_event(
                workflow_id,
                "step_failed",
                {"node_id": node_id, "attempts": self._retry_manager.max_retries, "error": str(exc)},
            )
            raise

    async def _dispatch_and_wait_node(
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

        successor_agents = []
        for successor in graph.successors(node_id):
            successor_data = graph.nodes[successor]
            successor_agents.append(
                successor_data.get("agent") or await self._agent_router.route(successor_data.get("task") or user_task)
            )

        predecessor_outputs = {
            predecessor: node_outputs.get(predecessor) for predecessor in graph.predecessors(node_id)
        }
        task_context = {
            **initial_context,
            "workflow_id": workflow_id,
            "node_id": node_id,
            "predecessor_outputs": predecessor_outputs,
            "tool": node_data.get("tool"),
            "successor_agents": successor_agents,
        }
        payload = {
            "workflow_id": workflow_id,
            "node_id": node_id,
            "agent": agent_name,
            "task": task,
            "context": task_context,
        }

        if self._rabbitmq_client.is_ready:
            queue_name = await self._task_dispatcher.dispatch(payload)
            await self._long_term_memory.save_agent_task(
                workflow_id=workflow_id,
                node_id=node_id,
                queue_name=queue_name,
                agent=agent_name,
                status="queued",
                payload=payload,
            )
        else:
            queue_name = "in_process_fallback"
            await self._long_term_memory.save_agent_task(
                workflow_id=workflow_id,
                node_id=node_id,
                queue_name=queue_name,
                agent=agent_name,
                status="dispatched_local",
                payload=payload,
            )
            await self._worker_manager.run_in_process(payload)

        output = await self._wait_for_node_result(workflow_id, node_id)
        if output is None:
            raise TimeoutError(f"Timed out waiting for result of node '{node_id}'")

        await self._long_term_memory.save_task_result(
            workflow_id=workflow_id,
            node_id=node_id,
            agent=agent_name,
            output=output,
            metadata={"queue_name": queue_name},
        )
        await self._context_manager.update_context(workflow_id, {f"{node_id}_result": output})
        return node_id, output

    async def _wait_for_node_result(self, workflow_id: str, node_id: str) -> dict[str, Any] | None:
        poll_interval = self._settings.workflow_result_poll_interval_seconds
        timeout = self._settings.workflow_result_timeout_seconds
        start = asyncio.get_running_loop().time()

        while True:
            output = await self._short_term_memory.get_node_output(workflow_id, node_id)
            if output is not None:
                return output

            elapsed = asyncio.get_running_loop().time() - start
            if elapsed >= timeout:
                return None

            await asyncio.sleep(poll_interval)

    async def _append_event(self, workflow_id: str, event_type: str, details: dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **details,
        }
        self._state_tracker.append_timeline(workflow_id, event)
        await self._context_manager.append_progress(workflow_id, event)
