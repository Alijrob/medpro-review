"""
ai.providers -- AI provider implementations for the narrative pipeline.

Providers:
    GeminiProvider    -- Google Gemini (research step)
    AnthropicProvider -- Anthropic Claude (analysis + format steps)

All providers accept an injectable ``client`` for tests (no live network).
When ``api_key`` is absent, providers silently return "" (FallbackProvider path).
"""
from .anthropic import AnthropicProvider
from .base import BaseAIProvider
from .gemini import GeminiProvider

__all__ = ["BaseAIProvider", "GeminiProvider", "AnthropicProvider"]
