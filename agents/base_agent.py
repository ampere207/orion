from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
