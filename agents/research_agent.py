from typing import Any

from llm.llm_interface import LLMInterface
from .base_agent import BaseAgent


class ResearchAgent(BaseAgent):
    name = "research_agent"
    description = "Retrieve external information and context"

    def __init__(self, llm_client: LLMInterface) -> None:
        self._llm_client = llm_client

    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        prompt = f"You are a research agent. Task: {task}. Context: {context}"
        text = await self._llm_client.generate_text(prompt)
        return {"agent": self.name, "output": text}
