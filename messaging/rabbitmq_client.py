from __future__ import annotations

import logging

import aio_pika
from aio_pika import Channel, Message, Queue

logger = logging.getLogger(__name__)


class RabbitMQClient:
    RESEARCH_QUEUE = "research_agent_queue"
    ANALYSIS_QUEUE = "analysis_agent_queue"
    CODE_QUEUE = "code_agent_queue"
    REPORT_QUEUE = "report_agent_queue"

    def __init__(self, rabbitmq_url: str) -> None:
        self._url = rabbitmq_url
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: Channel | None = None
        self._queues: dict[str, Queue] = {}
        self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    async def connect(self) -> None:
        try:
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=10)
            await self._declare_default_queues()
            self._is_ready = True
        except Exception:
            logger.exception("RabbitMQ not reachable. Queue dispatch will use in-process fallback.")
            self._is_ready = False

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()

    async def get_queue(self, queue_name: str) -> Queue:
        if not self._channel:
            raise RuntimeError("RabbitMQ channel is not initialized")
        if queue_name not in self._queues:
            self._queues[queue_name] = await self._channel.declare_queue(queue_name, durable=True)
        return self._queues[queue_name]

    async def publish(self, queue_name: str, payload: bytes) -> None:
        if not self._channel:
            raise RuntimeError("RabbitMQ channel is not initialized")
        await self._channel.default_exchange.publish(Message(body=payload, delivery_mode=2), routing_key=queue_name)

    async def _declare_default_queues(self) -> None:
        for queue_name in [
            self.RESEARCH_QUEUE,
            self.ANALYSIS_QUEUE,
            self.CODE_QUEUE,
            self.REPORT_QUEUE,
        ]:
            self._queues[queue_name] = await self._channel.declare_queue(queue_name, durable=True)