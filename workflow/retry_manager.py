from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class RetryManager:
    def __init__(self, max_retries: int = 3, retry_delay_seconds: float = 0.2) -> None:
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

    @property
    def max_retries(self) -> int:
        return self._max_retries

    async def run(self, operation: Callable[[], Awaitable[Any]]) -> tuple[Any, int]:
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return await operation(), attempt
            except Exception as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._retry_delay_seconds)

        if last_error is not None:
            raise last_error

        raise RuntimeError("Retry manager failed without capturing an exception")