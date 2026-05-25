"""
stores.py — in-memory backing stores (SHELL ONLY).

Process-local stand-ins for the Redis-backed stores used in deployment:
  TTLStore        -> idempotency response cache (Redis SET ... EX)
  FixedWindowLimiter -> rate limiter (Redis INCR + EXPIRE per window)

Non-durable and single-replica only. When `redis_url` is set the gateway swaps
these for Redis-backed implementations; until then this keeps the shell runnable
with no external dependency. Reset between tests via reset_stores().
"""
from __future__ import annotations

import time
from typing import Any


class TTLStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.time() >= expires_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._data[key] = (time.time() + ttl_seconds, value)

    def clear(self) -> None:
        self._data.clear()


class FixedWindowLimiter:
    """Fixed-window counter. Returns (allowed, retry_after_seconds)."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, int], int] = {}

    def check(self, client_id: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        window_start = int(now // window_seconds) * window_seconds
        bucket = (client_id, window_start)
        count = self._counters.get(bucket, 0) + 1
        self._counters[bucket] = count
        if count > limit:
            retry_after = int(window_start + window_seconds - now) + 1
            return False, max(retry_after, 1)
        return True, 0

    def clear(self) -> None:
        self._counters.clear()


# Module-level singletons (shell). Swapped for Redis-backed when redis_url is set.
idempotency_store = TTLStore()
rate_limiter = FixedWindowLimiter()


def reset_stores() -> None:
    idempotency_store.clear()
    rate_limiter.clear()
