"""
anthropic.py -- AnthropicProvider: Claude models via Anthropic SDK.

Used for both the analysis step (Opus) and format step (Haiku).
Supports injectable client for unit testing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import BaseAIProvider

log = logging.getLogger(__name__)


class AnthropicProvider(BaseAIProvider):
    """
    Anthropic Claude provider using the anthropic SDK.

    Args:
        api_key: Anthropic API key. None -> FallbackProvider mode.
        client:  Injectable callable ``(prompt, *, model, max_tokens) -> str | Awaitable[str]``
                 used in tests to avoid live network calls.
    """

    def __init__(self, api_key: str | None, *, client: Any = None) -> None:
        self._api_key = api_key
        self._client = client

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def complete(self, prompt: str, *, max_tokens: int, model: str) -> str:
        if not self.is_available:
            return ""

        # Injectable client path (tests)
        if self._client is not None:
            try:
                result = self._client(prompt, model=model, max_tokens=max_tokens)
                if asyncio.iscoroutine(result):
                    return await result
                return str(result)
            except Exception as exc:  # noqa: BLE001
                log.warning("AnthropicProvider injected client error: %s", exc)
                return ""

        # Real SDK path
        try:
            import anthropic  # type: ignore[import-untyped]

            async_client = anthropic.AsyncAnthropic(api_key=self._api_key)
            message = await async_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as exc:  # noqa: BLE001
            log.warning("AnthropicProvider API error model=%s: %s", model, exc)
            return ""
