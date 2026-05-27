"""
router.py -- Top-level generate_narrative() convenience function.

Combines PII scrubbing, NarrativeGenerator, and settings into a single
callable. This is the public entry point used by the Temporal activity.
"""
from __future__ import annotations

from typing import Any

from .config import AISettings
from .models import NarrativeResult
from .narrative import NarrativeGenerator
from .providers import AnthropicProvider, GeminiProvider


async def generate_narrative(
    npi: str,
    profile: dict[str, Any],
    settings: AISettings,
    *,
    gemini: GeminiProvider | None = None,
    anthropic: AnthropicProvider | None = None,
) -> NarrativeResult:
    """
    Generate an AI narrative for a provider profile.

    This is the primary entry point called by generate_ai_narrative_activity.
    PII scrubbing happens inside NarrativeGenerator.generate().

    Args:
        npi:       Provider NPI.
        profile:   Raw profile dict (PII will be stripped before any prompt).
        settings:  AISettings with model config + API keys.
        gemini:    Optional GeminiProvider override (for tests).
        anthropic: Optional AnthropicProvider override (for tests).

    Returns:
        NarrativeResult (fallback=True if any provider was unavailable).
    """
    generator = NarrativeGenerator(settings, gemini=gemini, anthropic=anthropic)
    return await generator.generate(npi, profile)
