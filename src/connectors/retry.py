"""
retry.py — exponential backoff with full jitter (component C9).

In-house (no `tenacity`): the locked stack names `httpx` for HTTP and nothing for
retry, so the framework keeps it dependency-free and fully injectable. Only
`ConnectorError`s flagged `retryable` are retried; a `RateLimitedError.retry_after`
sets a floor on the delay. `sleep` and `rng` are injected so tests are deterministic.
"""
from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .errors import ConnectorError, RateLimitedError

T = TypeVar("T")


async def retry_with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rng: Callable[[], float] = random.random,  # noqa: S311 (jitter, not crypto)
    on_retry: Callable[[int, ConnectorError], None] | None = None,
) -> T:
    """Call `fn`, retrying retryable ConnectorErrors up to `max_retries` times."""
    attempt = 0
    while True:
        try:
            return await fn()
        except ConnectorError as exc:
            if not exc.retryable or attempt >= max_retries:
                raise
            # Exponential base with full jitter: delay in [0, base * 2**attempt].
            ceiling = min(max_delay, base_delay * (2 ** attempt))
            delay = rng() * ceiling
            if isinstance(exc, RateLimitedError) and exc.retry_after is not None:
                delay = max(delay, exc.retry_after)
            attempt += 1
            if on_retry is not None:
                on_retry(attempt, exc)
            await sleep(delay)
