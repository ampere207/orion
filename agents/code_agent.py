from typing import Any

from llm.llm_interface import LLMInterface
from .base_agent import BaseAgent


class CodeAgent(BaseAgent):
    name = "code_agent"
    description = "Generate or reason about code snippets"

    def __init__(self, llm_client: LLMInterface) -> None:
        self._llm_client = llm_client

    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        prompt = f"You are a code agent. Task: {task}. Context: {context}"
        text = await self._llm_client.generate_text(prompt)
        return {"agent": self.name, "output": text}
