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
