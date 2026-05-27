"""
test_providers.py -- Tests for ai.providers (Phase 4-H).

All tests use injectable clients -- no live API calls.

Run:
    PYTHONPATH=src:. pytest tests/ai/test_providers.py -v
"""
from __future__ import annotations

import asyncio

import pytest

from ai.providers import AnthropicProvider, GeminiProvider
from ai.providers.base import BaseAIProvider


# ---------------------------------------------------------------------------
# BaseAIProvider
# ---------------------------------------------------------------------------

class TestBaseAIProvider:
    def test_is_abstract(self):
        """BaseAIProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAIProvider()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# GeminiProvider
# ---------------------------------------------------------------------------

class TestGeminiProviderAvailability:
    def test_not_available_when_no_key(self):
        p = GeminiProvider(api_key=None)
        assert p.is_available is False

    def test_available_when_key_set(self):
        p = GeminiProvider(api_key="test-key")
        assert p.is_available is True

    def test_complete_returns_empty_when_unavailable(self):
        p = GeminiProvider(api_key=None)
        result = asyncio.run(p.complete("prompt", max_tokens=100, model="gemini-2.5-pro"))
        assert result == ""


class TestGeminiProviderWithInjectableClient:
    def test_calls_client_with_prompt(self):
        calls = []

        def _client(prompt, *, model, max_tokens):
            calls.append({"prompt": prompt, "model": model, "max_tokens": max_tokens})
            return "research context output"

        p = GeminiProvider(api_key="key", client=_client)
        result = asyncio.run(p.complete("test prompt", max_tokens=512, model="gemini-2.5-pro"))
        assert result == "research context output"
        assert calls[0]["prompt"] == "test prompt"
        assert calls[0]["model"] == "gemini-2.5-pro"
        assert calls[0]["max_tokens"] == 512

    def test_returns_client_response_text(self):
        p = GeminiProvider(api_key="key", client=lambda *a, **kw: "response text")
        result = asyncio.run(p.complete("x", max_tokens=100, model="m"))
        assert result == "response text"

    def test_client_exception_returns_empty(self):
        def _bad_client(prompt, *, model, max_tokens):
            raise RuntimeError("API failure")

        p = GeminiProvider(api_key="key", client=_bad_client)
        result = asyncio.run(p.complete("x", max_tokens=100, model="m"))
        assert result == ""

    def test_async_client_supported(self):
        async def _async_client(prompt, *, model, max_tokens):
            return "async result"

        p = GeminiProvider(api_key="key", client=_async_client)
        result = asyncio.run(p.complete("x", max_tokens=100, model="m"))
        assert result == "async result"


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------

class TestAnthropicProviderAvailability:
    def test_not_available_when_no_key(self):
        p = AnthropicProvider(api_key=None)
        assert p.is_available is False

    def test_available_when_key_set(self):
        p = AnthropicProvider(api_key="test-key")
        assert p.is_available is True

    def test_complete_returns_empty_when_unavailable(self):
        p = AnthropicProvider(api_key=None)
        result = asyncio.run(p.complete("prompt", max_tokens=100, model="claude-opus-4-7"))
        assert result == ""


class TestAnthropicProviderWithInjectableClient:
    def test_calls_client_with_prompt(self):
        calls = []

        def _client(prompt, *, model, max_tokens):
            calls.append({"prompt": prompt, "model": model, "max_tokens": max_tokens})
            return "[RISK_ANALYSIS]\nlow risk\n[END_RISK_ANALYSIS]\n[CONSUMER_SUMMARY]\nok\n[END_CONSUMER_SUMMARY]"

        p = AnthropicProvider(api_key="key", client=_client)
        result = asyncio.run(p.complete("analysis prompt", max_tokens=1024, model="claude-opus-4-7"))
        assert "low risk" in result
        assert calls[0]["model"] == "claude-opus-4-7"
        assert calls[0]["max_tokens"] == 1024

    def test_returns_client_response_text(self):
        p = AnthropicProvider(api_key="key", client=lambda *a, **kw: "formatted text")
        result = asyncio.run(p.complete("x", max_tokens=100, model="m"))
        assert result == "formatted text"

    def test_client_exception_returns_empty(self):
        def _bad_client(prompt, *, model, max_tokens):
            raise ConnectionError("network failure")

        p = AnthropicProvider(api_key="key", client=_bad_client)
        result = asyncio.run(p.complete("x", max_tokens=100, model="m"))
        assert result == ""

    def test_async_client_supported(self):
        async def _async_client(prompt, *, model, max_tokens):
            return "async response"

        p = AnthropicProvider(api_key="key", client=_async_client)
        result = asyncio.run(p.complete("x", max_tokens=100, model="m"))
        assert result == "async response"
