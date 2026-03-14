from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self, redis_url: str) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._fallback: dict[str, str] = {}
        self._is_ready = False

    async def connect(self) -> None:
        try:
            await self._client.ping()
            self._is_ready = True
        except Exception:
            logger.exception("Redis not ready, falling back to in-memory memory store.")
            self._is_ready = False

    async def set_json(self, key: str, value: dict[str, Any]) -> None:
        payload = json.dumps(value)
        if self._is_ready:
            await self._client.set(key, payload)
            return
        self._fallback[key] = payload

    async def get_json(self, key: str) -> dict[str, Any] | None:
        if self._is_ready:
            raw = await self._client.get(key)
        else:
            raw = self._fallback.get(key)
        if raw is None:
            return None
        return json.loads(raw)
