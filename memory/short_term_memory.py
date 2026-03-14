from typing import Any

from db.redis_client import RedisClient


class ShortTermMemory:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis_client = redis_client

    async def set_node_output(self, workflow_id: str, node_id: str, output: dict[str, Any]) -> None:
        key = f"workflow:{workflow_id}:node:{node_id}"
        await self._redis_client.set_json(key, output)

    async def get_node_output(self, workflow_id: str, node_id: str) -> dict[str, Any] | None:
        key = f"workflow:{workflow_id}:node:{node_id}"
        return await self._redis_client.get_json(key)
