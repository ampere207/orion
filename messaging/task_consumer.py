from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from aio_pika import IncomingMessage

from messaging.rabbitmq_client import RabbitMQClient


class TaskConsumer:
    def __init__(self, rabbitmq_client: RabbitMQClient) -> None:
        self._rabbitmq_client = rabbitmq_client

    async def consume(self, queue_name: str, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        queue = await self._rabbitmq_client.get_queue(queue_name)

        async def _on_message(message: IncomingMessage) -> None:
            async with message.process(ignore_processed=True):
                payload = json.loads(message.body.decode("utf-8"))
                await handler(payload)

        await queue.consume(_on_message)