from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base, WorkflowRecord

logger = logging.getLogger(__name__)


class PostgresClient:
    def __init__(self, postgres_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(postgres_url, echo=False, future=True)
        self._session_factory = async_sessionmaker(bind=self._engine, class_=AsyncSession, expire_on_commit=False)
        self._fallback_store: dict[str, dict[str, Any]] = {}
        self._is_ready = False

    async def init_models(self) -> None:
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self._is_ready = True
        except Exception:
            logger.exception("PostgreSQL not ready, falling back to in-memory workflow persistence.")
            self._is_ready = False

    async def save_workflow(self, workflow_id: str, status: str, input_task: str, result: str | None, error: str | None) -> None:
        if not self._is_ready:
            self._fallback_store[workflow_id] = {
                "workflow_id": workflow_id,
                "status": status,
                "input_task": input_task,
                "result": result,
                "error": error,
            }
            return

        async with self._session_factory() as session:
            existing = await session.get(WorkflowRecord, workflow_id)
            if existing:
                existing.status = status
                existing.input_task = input_task
                existing.result = result
                existing.error = error
            else:
                session.add(
                    WorkflowRecord(
                        workflow_id=workflow_id,
                        status=status,
                        input_task=input_task,
                        result=result,
                        error=error,
                    )
                )
            await session.commit()

    async def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        if not self._is_ready:
            return self._fallback_store.get(workflow_id)

        async with self._session_factory() as session:
            stmt = select(WorkflowRecord).where(WorkflowRecord.workflow_id == workflow_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if not record:
                return None
            return {
                "workflow_id": record.workflow_id,
                "status": record.status,
                "input_task": record.input_task,
                "result": record.result,
                "error": record.error,
            }
