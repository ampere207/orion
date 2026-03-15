from typing import Any

from db.postgres import PostgresClient


class LongTermMemory:
    def __init__(self, postgres_client: PostgresClient) -> None:
        self._postgres_client = postgres_client

    async def save_workflow_history(
        self,
        workflow_id: str,
        status: str,
        input_task: str,
        result: str | None = None,
        error: str | None = None,
    ) -> None:
        await self._postgres_client.save_workflow(
            workflow_id=workflow_id,
            status=status,
            input_task=input_task,
            result=result,
            error=error,
        )

    async def get_workflow_history(self, workflow_id: str) -> dict[str, Any] | None:
        return await self._postgres_client.get_workflow(workflow_id)

    async def save_workflow_step(
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
        await self._postgres_client.upsert_workflow_step(
            workflow_id=workflow_id,
            node_id=node_id,
            agent=agent,
            task=task,
            status=status,
            attempts=attempts,
            tool=tool,
            depends_on=depends_on,
            output=output,
            error=error,
        )

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
        await self._postgres_client.save_agent_task(
            workflow_id=workflow_id,
            node_id=node_id,
            queue_name=queue_name,
            agent=agent,
            status=status,
            payload=payload,
            error=error,
        )

    async def save_task_result(
        self,
        workflow_id: str,
        node_id: str,
        agent: str,
        output: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._postgres_client.save_task_result(
            workflow_id=workflow_id,
            node_id=node_id,
            agent=agent,
            output=output,
            metadata=metadata,
        )
