from abc import ABC, abstractmethod
from typing import Any


class LLMInterface(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def plan_task(self, task: str) -> dict[str, Any]:
        raise NotImplementedError
