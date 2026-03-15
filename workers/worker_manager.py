from __future__ import annotations

import asyncio
import logging
from typing import Any

from agent_registry.registry import AgentRegistry
from memory.context_manager import ContextManager
from memory.short_term_memory import ShortTermMemory
from messaging.rabbitmq_client import RabbitMQClient
from messaging.task_consumer import TaskConsumer
from workers.analysis_worker import AnalysisWorker
from workers.code_worker import CodeWorker
from workers.report_worker import ReportWorker
from workers.research_worker import ResearchWorker

logger = logging.getLogger(__name__)


class WorkerManager:
    def __init__(
        self,
        rabbitmq_client: RabbitMQClient,
        task_consumer: TaskConsumer,
        agent_registry: AgentRegistry,
        short_term_memory: ShortTermMemory,
        context_manager: ContextManager,
    ) -> None:
        self._rabbitmq_client = rabbitmq_client
        self._task_consumer = task_consumer
        self._research_worker = ResearchWorker(agent_registry, short_term_memory, context_manager)
        self._analysis_worker = AnalysisWorker(agent_registry, short_term_memory, context_manager)
        self._code_worker = CodeWorker(agent_registry, short_term_memory, context_manager)
        self._report_worker = ReportWorker(agent_registry, short_term_memory, context_manager)
        self._started = False

    async def start(self) -> None:
        if self._started or not self._rabbitmq_client.is_ready:
            return

        await self._task_consumer.consume(RabbitMQClient.RESEARCH_QUEUE, self._research_worker.handle)
        await self._task_consumer.consume(RabbitMQClient.ANALYSIS_QUEUE, self._analysis_worker.handle)
        await self._task_consumer.consume(RabbitMQClient.CODE_QUEUE, self._code_worker.handle)
        await self._task_consumer.consume(RabbitMQClient.REPORT_QUEUE, self._report_worker.handle)
        self._started = True
        logger.info("RabbitMQ worker consumers are running.")

    async def run_in_process(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent = payload["agent"]
        if agent == "research_agent":
            return await self._research_worker.handle(payload)
        if agent == "analysis_agent":
            return await self._analysis_worker.handle(payload)
        if agent == "code_agent":
            return await self._code_worker.handle(payload)
        if agent == "report_agent":
            return await self._report_worker.handle(payload)
        raise KeyError(f"Unsupported agent worker: {agent}")