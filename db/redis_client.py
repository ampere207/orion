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

    async def append_json_list(self, key: str, value: dict[str, Any]) -> None:
        if self._is_ready:
            await self._client.rpush(key, json.dumps(value))
            return

        existing = json.loads(self._fallback.get(key, "[]"))
        existing.append(value)
        self._fallback[key] = json.dumps(existing)

    async def get_json_list(self, key: str) -> list[dict[str, Any]]:
        if self._is_ready:
            raw_items = await self._client.lrange(key, 0, -1)
            return [json.loads(item) for item in raw_items]

        raw = self._fallback.get(key, "[]")
        return json.loads(raw)
