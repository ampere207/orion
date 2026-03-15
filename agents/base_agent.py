from abc import ABC, abstractmethod
from typing import Any

from agents.agent_messaging import AgentMessaging
from llm.llm_interface import LLMInterface
from memory.context_manager import ContextManager
from tools.tool_registry import ToolRegistry


class BaseAgent(ABC):
    name: str
    description: str

    def __init__(
        self,
        llm_client: LLMInterface,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
        messaging: AgentMessaging,
    ) -> None:
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._context_manager = context_manager
        self._messaging = messaging

    async def use_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = self._tool_registry.get_tool(tool_name)
        return await tool.execute(params)

    async def read_shared_context(self, workflow_id: str) -> dict[str, Any]:
        return await self._context_manager.get_context(workflow_id)

    async def update_shared_context(self, workflow_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return await self._context_manager.update_context(workflow_id, values)

    async def send_message(self, receiver: str, task_id: str, content: str) -> dict[str, Any]:
        return await self._messaging.send_message(self.name, receiver, task_id, content)

    async def receive_messages(self, task_id: str) -> list[dict[str, Any]]:
        return await self._messaging.receive_messages(self.name, task_id)

    async def _notify_successors(self, workflow_id: str, context: dict[str, Any], summary: str) -> list[dict[str, Any]]:
        sent_messages: list[dict[str, Any]] = []
        for successor in context.get("successor_agents", []):
            sent_messages.append(await self.send_message(successor, workflow_id, summary))
        return sent_messages

    @abstractmethod
    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
