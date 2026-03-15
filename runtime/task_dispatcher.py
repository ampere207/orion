from __future__ import annotations

from typing import Any

from messaging.rabbitmq_client import RabbitMQClient
from messaging.task_publisher import TaskPublisher


class TaskDispatcher:
    def __init__(self, task_publisher: TaskPublisher) -> None:
        self._task_publisher = task_publisher
        self._queue_map = {
            "research_agent": RabbitMQClient.RESEARCH_QUEUE,
            "analysis_agent": RabbitMQClient.ANALYSIS_QUEUE,
            "code_agent": RabbitMQClient.CODE_QUEUE,
            "report_agent": RabbitMQClient.REPORT_QUEUE,
        }

    def get_queue_name(self, agent_name: str) -> str:
        if agent_name not in self._queue_map:
            raise KeyError(f"No queue mapping for agent '{agent_name}'")
        return self._queue_map[agent_name]

    async def dispatch(self, payload: dict[str, Any]) -> str:
        agent_name = str(payload["agent"])
        queue_name = self.get_queue_name(agent_name)
        await self._task_publisher.publish_task(queue_name, payload)
        return queue_name