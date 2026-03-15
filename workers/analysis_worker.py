from __future__ import annotations

from typing import Any

from agent_registry.registry import AgentRegistry
from memory.context_manager import ContextManager
from memory.short_term_memory import ShortTermMemory


class AnalysisWorker:
    agent_name = "analysis_agent"

    def __init__(self, agent_registry: AgentRegistry, short_term_memory: ShortTermMemory, context_manager: ContextManager) -> None:
        self._agent_registry = agent_registry
        self._short_term_memory = short_term_memory
        self._context_manager = context_manager

    async def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent = self._agent_registry.get_agent(self.agent_name)
        output = await agent.execute(payload["task"], payload["context"])
        await self._short_term_memory.set_node_output(payload["workflow_id"], payload["node_id"], output)
        await self._context_manager.update_context(payload["workflow_id"], {f"{payload['node_id']}_result": output})
        return output