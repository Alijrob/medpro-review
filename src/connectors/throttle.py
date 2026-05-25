"""
throttle.py — client-side rate limiting (component C9).

A minimal-interval limiter: spaces requests so the source's rate limit is respected
before the source has to 429 us. The clock and sleep are injectable so tests are
deterministic and need no real time. In deployed multi-replica adapters this is the
per-replica floor; a Redis-backed global limiter (ElastiCache) is layered on later.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class RateLimiter:
    """Allow at most `rate_per_sec` acquisitions per second (per instance)."""

    def __init__(
        self,
        rate_per_sec: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._min_interval = (1.0 / rate_per_sec) if rate_per_sec > 0 else 0.0
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    async def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        now = self._clock()
        if self._last is not None:
            wait = self._min_interval - (now - self._last)
            if wait > 0:
                await self._sleep(wait)
        self._last = self._clock()
