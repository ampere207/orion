from __future__ import annotations

import asyncio
from typing import Any

import networkx as nx

from agent_registry.registry import AgentRegistry
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from workflow.workflow_state import WorkflowState, WorkflowStateTracker


class WorkflowExecutor:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
        state_tracker: WorkflowStateTracker,
    ) -> None:
        self._agent_registry = agent_registry
        self._short_term_memory = short_term_memory
        self._long_term_memory = long_term_memory
        self._state_tracker = state_tracker

    async def execute(
        self,
        workflow_id: str,
        user_task: str,
        graph: nx.DiGraph,
        initial_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._state_tracker.update(workflow_id, WorkflowState.RUNNING)
        await self._long_term_memory.save_workflow_history(workflow_id, WorkflowState.RUNNING.value, user_task)

        node_outputs: dict[str, dict[str, Any]] = {}
        completed: set[str] = set()
        in_progress: set[str] = set()

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
                        self._run_node(
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
                for node_id, output in results:
                    node_outputs[node_id] = output
                    completed.add(node_id)
                    in_progress.discard(node_id)

            ordered_nodes = list(nx.topological_sort(graph))
            final_output = node_outputs.get(ordered_nodes[-1], {"output": ""})

            self._state_tracker.update(
                workflow_id,
                WorkflowState.COMPLETED,
                details={"result": final_output.get("output", "")},
            )
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
                "node_outputs": node_outputs,
            }
        except Exception as exc:
            self._state_tracker.update(workflow_id, WorkflowState.FAILED, details={"error": str(exc)})
            await self._long_term_memory.save_workflow_history(
                workflow_id,
                WorkflowState.FAILED.value,
                user_task,
                error=str(exc),
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
        agent_name = node_data.get("agent")
        task = node_data.get("task") or user_task

        agent = self._agent_registry.get_agent(agent_name)

        predecessor_outputs = {
            predecessor: node_outputs.get(predecessor) for predecessor in graph.predecessors(node_id)
        }
        context = {
            **initial_context,
            "workflow_id": workflow_id,
            "node_id": node_id,
            "predecessor_outputs": predecessor_outputs,
        }

        output = await agent.execute(task, context)
        await self._short_term_memory.set_node_output(workflow_id, node_id, output)
        return node_id, output
