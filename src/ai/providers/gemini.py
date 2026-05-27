"""
gemini.py -- GeminiProvider: Google Gemini via google-genai SDK.

Used for the research step (Step 1) of the narrative pipeline.
Supports injectable client for unit testing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import BaseAIProvider

log = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini provider using the google-genai SDK.

    Args:
        api_key: Google AI Studio API key. None -> FallbackProvider mode.
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
                log.warning("GeminiProvider injected client error: %s", exc)
                return ""

        # Real SDK path
        try:
            from google import genai  # type: ignore[import-untyped]
            from google.genai import types  # type: ignore[import-untyped]

            client = genai.Client(api_key=self._api_key)
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text or ""
        except Exception as exc:  # noqa: BLE001
            log.warning("GeminiProvider API error model=%s: %s", model, exc)
            return ""
