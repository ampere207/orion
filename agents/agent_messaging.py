from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from db.redis_client import RedisClient


class AgentMessaging:
    def __init__(self, redis_client: RedisClient) -> None:
        self._redis_client = redis_client

    def _message_key(self, task_id: str, receiver: str) -> str:
        return f"workflow:{task_id}:messages:{receiver}"

    async def send_message(self, sender: str, receiver: str, task_id: str, content: str) -> dict[str, Any]:
        message = {
            "sender": sender,
            "receiver": receiver,
            "task_id": task_id,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._redis_client.append_json_list(self._message_key(task_id, receiver), message)
        return message

    async def receive_messages(self, receiver: str, task_id: str) -> list[dict[str, Any]]:
        return await self._redis_client.get_json_list(self._message_key(task_id, receiver))