from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from db.redis_client import RedisClient


class ContextManager:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis_client = redis_client

    def _context_key(self, workflow_id: str) -> str:
        return f"workflow:{workflow_id}:context"

    def _progress_key(self, workflow_id: str) -> str:
        return f"workflow:{workflow_id}:progress"

    async def get_context(self, workflow_id: str) -> dict[str, Any]:
        context = await self._redis_client.get_json(self._context_key(workflow_id))
        return context or {}

    async def update_context(self, workflow_id: str, values: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_context(workflow_id)
        updated = {**current, **values}
        await self._redis_client.set_json(self._context_key(workflow_id), updated)
        return updated

    async def append_progress(self, workflow_id: str, entry: dict[str, Any]) -> None:
        progress_entry = {
            **entry,
            "timestamp": entry.get("timestamp") or datetime.now(UTC).isoformat(),
        }
        await self._redis_client.append_json_list(self._progress_key(workflow_id), progress_entry)

    async def get_progress(self, workflow_id: str) -> list[dict[str, Any]]:
        return await self._redis_client.get_json_list(self._progress_key(workflow_id))