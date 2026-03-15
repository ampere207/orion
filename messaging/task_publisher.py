from __future__ import annotations

import json
from typing import Any

from messaging.rabbitmq_client import RabbitMQClient


class TaskPublisher:
    def __init__(self, rabbitmq_client: RabbitMQClient) -> None:
        self._rabbitmq_client = rabbitmq_client

    async def publish_task(self, queue_name: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        await self._rabbitmq_client.publish(queue_name, body)