from __future__ import annotations

import logging
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from db.models import AgentTaskRecord, Base, TaskResultRecord, WorkflowRecord, WorkflowStepRecord

logger = logging.getLogger(__name__)


class PostgresClient:
    def __init__(self, postgres_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(postgres_url, echo=False, future=True)
        self._session_factory = async_sessionmaker(bind=self._engine, class_=AsyncSession, expire_on_commit=False)
        self._fallback_store: dict[str, dict[str, Any]] = {}
        self._fallback_steps: dict[str, dict[str, dict[str, Any]]] = {}
        self._fallback_agent_tasks: dict[str, list[dict[str, Any]]] = {}
        self._fallback_results: dict[str, list[dict[str, Any]]] = {}
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

    async def upsert_workflow_step(
        self,
        workflow_id: str,
        node_id: str,
        agent: str,
        task: str,
        status: str,
        attempts: int,
        tool: str | None = None,
        depends_on: list[str] | None = None,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        payload_output = json.dumps(output) if output is not None else None
        payload_depends = json.dumps(depends_on or [])

        if not self._is_ready:
            self._fallback_steps.setdefault(workflow_id, {})[node_id] = {
                "workflow_id": workflow_id,
                "node_id": node_id,
                "agent": agent,
                "task": task,
                "tool": tool,
                "depends_on": depends_on or [],
                "status": status,
                "attempts": attempts,
                "output": output,
                "error": error,
            }
            return

        async with self._session_factory() as session:
            stmt = select(WorkflowStepRecord).where(
                WorkflowStepRecord.workflow_id == workflow_id,
                WorkflowStepRecord.node_id == node_id,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.agent = agent
                existing.task = task
                existing.tool = tool
                existing.depends_on = payload_depends
                existing.status = status
                existing.attempts = attempts
                existing.output = payload_output
                existing.error = error
            else:
                session.add(
                    WorkflowStepRecord(
                        workflow_id=workflow_id,
                        node_id=node_id,
                        agent=agent,
                        task=task,
                        tool=tool,
                        depends_on=payload_depends,
                        status=status,
                        attempts=attempts,
                        output=payload_output,
                        error=error,
                    )
                )
            await session.commit()

    async def save_agent_task(
        self,
        workflow_id: str,
        node_id: str,
        queue_name: str,
        agent: str,
        status: str,
        payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        serialized = json.dumps(payload) if payload is not None else None
        if not self._is_ready:
            self._fallback_agent_tasks.setdefault(workflow_id, []).append(
                {
                    "workflow_id": workflow_id,
                    "node_id": node_id,
                    "queue_name": queue_name,
                    "agent": agent,
                    "status": status,
                    "payload": payload,
                    "error": error,
                }
            )
            return

        async with self._session_factory() as session:
            session.add(
                AgentTaskRecord(
                    workflow_id=workflow_id,
                    node_id=node_id,
                    queue_name=queue_name,
                    agent=agent,
                    status=status,
                    payload=serialized,
                    error=error,
                )
            )
            await session.commit()

    async def save_task_result(
        self,
        workflow_id: str,
        node_id: str,
        agent: str,
        output: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._is_ready:
            self._fallback_results.setdefault(workflow_id, []).append(
                {
                    "workflow_id": workflow_id,
                    "node_id": node_id,
                    "agent": agent,
                    "output": output,
                    "metadata": metadata or {},
                }
            )
            return

        async with self._session_factory() as session:
            session.add(
                TaskResultRecord(
                    workflow_id=workflow_id,
                    node_id=node_id,
                    agent=agent,
                    output=json.dumps(output) if output is not None else None,
                    metadata_json=json.dumps(metadata or {}),
                )
            )
            await session.commit()

    async def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        if not self._is_ready:
            workflow = self._fallback_store.get(workflow_id)
            if not workflow:
                return None
            return {
                **workflow,
                "steps": list(self._fallback_steps.get(workflow_id, {}).values()),
                "agent_tasks": self._fallback_agent_tasks.get(workflow_id, []),
                "task_results": self._fallback_results.get(workflow_id, []),
            }

        async with self._session_factory() as session:
            stmt = select(WorkflowRecord).where(WorkflowRecord.workflow_id == workflow_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if not record:
                return None

            step_rows = (
                await session.execute(
                    select(WorkflowStepRecord).where(WorkflowStepRecord.workflow_id == workflow_id)
                )
            ).scalars().all()
            task_rows = (
                await session.execute(select(AgentTaskRecord).where(AgentTaskRecord.workflow_id == workflow_id))
            ).scalars().all()
            result_rows = (
                await session.execute(select(TaskResultRecord).where(TaskResultRecord.workflow_id == workflow_id))
            ).scalars().all()

            return {
                "workflow_id": record.workflow_id,
                "status": record.status,
                "input_task": record.input_task,
                "result": record.result,
                "error": record.error,
                "steps": [
                    {
                        "node_id": row.node_id,
                        "agent": row.agent,
                        "task": row.task,
                        "tool": row.tool,
                        "depends_on": json.loads(row.depends_on) if row.depends_on else [],
                        "status": row.status,
                        "attempts": row.attempts,
                        "output": json.loads(row.output) if row.output else None,
                        "error": row.error,
                    }
                    for row in step_rows
                ],
                "agent_tasks": [
                    {
                        "node_id": row.node_id,
                        "queue_name": row.queue_name,
                        "agent": row.agent,
                        "status": row.status,
                        "payload": json.loads(row.payload) if row.payload else None,
                        "error": row.error,
                    }
                    for row in task_rows
                ],
                "task_results": [
                    {
                        "node_id": row.node_id,
                        "agent": row.agent,
                        "output": json.loads(row.output) if row.output else None,
                        "metadata": json.loads(row.metadata_json) if row.metadata_json else {},
                    }
                    for row in result_rows
                ],
            }
