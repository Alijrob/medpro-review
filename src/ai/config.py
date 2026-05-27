"""
config.py -- AISettings: API keys and model configuration for the AI narrative layer.

Env prefix: AI_
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class AISettings(BaseSettings):
    """
    Configuration for the multi-model AI narrative pipeline.

    All settings default to None / disabled so the service starts without
    env vars and degrades gracefully (FallbackProvider path).
    """

    # API keys -- absent = FallbackProvider (silent empty return)
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model IDs -- overridable per-env
    research_model: str = "gemini-2.5-pro"
    analysis_model: str = "claude-opus-4-7"
    format_model: str = "claude-haiku-4-5-20251001"

    # Token budgets
    research_max_tokens: int = 4096
    analysis_max_tokens: int = 2048
    format_max_tokens: int = 1024

    # Feature flag -- set AI_NARRATIVE_ENABLED=false to bypass the step entirely
    narrative_enabled: bool = True

    model_config = {"env_prefix": "AI_", "case_sensitive": False}


@lru_cache(maxsize=1)
def get_ai_settings() -> AISettings:
    return AISettings()
