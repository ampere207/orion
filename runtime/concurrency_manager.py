from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


class ConcurrencyManager:
    def __init__(self, max_concurrent_tasks: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async def run(self, operation: Awaitable[T]) -> T:
        async with self._semaphore:
            return await operation