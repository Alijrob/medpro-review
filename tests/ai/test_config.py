"""
test_config.py -- Tests for ai.config.AISettings (Phase 4-H).

Run:
    PYTHONPATH=src:. pytest tests/ai/test_config.py -v
"""
from __future__ import annotations

import pytest

from ai.config import AISettings


class TestAISettingsDefaults:
    def test_gemini_api_key_defaults_to_none(self):
        cfg = AISettings()
        assert cfg.gemini_api_key is None

    def test_anthropic_api_key_defaults_to_none(self):
        cfg = AISettings()
        assert cfg.anthropic_api_key is None

    def test_narrative_enabled_defaults_true(self):
        cfg = AISettings()
        assert cfg.narrative_enabled is True

    def test_research_model_default(self):
        cfg = AISettings()
        assert cfg.research_model == "gemini-2.5-pro"

    def test_analysis_model_default(self):
        cfg = AISettings()
        assert cfg.analysis_model == "claude-opus-4-7"

    def test_format_model_default(self):
        cfg = AISettings()
        assert cfg.format_model == "claude-haiku-4-5-20251001"

    def test_research_max_tokens_default(self):
        cfg = AISettings()
        assert cfg.research_max_tokens == 4096

    def test_analysis_max_tokens_default(self):
        cfg = AISettings()
        assert cfg.analysis_max_tokens == 2048

    def test_format_max_tokens_default(self):
        cfg = AISettings()
        assert cfg.format_max_tokens == 1024


class TestAISettingsOverrides:
    def test_gemini_key_override(self):
        cfg = AISettings(gemini_api_key="test-gemini-key")
        assert cfg.gemini_api_key == "test-gemini-key"

    def test_anthropic_key_override(self):
        cfg = AISettings(anthropic_api_key="test-anthropic-key")
        assert cfg.anthropic_api_key == "test-anthropic-key"

    def test_narrative_disabled_via_override(self):
        cfg = AISettings(narrative_enabled=False)
        assert cfg.narrative_enabled is False

    def test_model_id_override(self):
        cfg = AISettings(research_model="gemini-2.5-flash")
        assert cfg.research_model == "gemini-2.5-flash"

    def test_env_prefix_is_ai(self, monkeypatch):
        monkeypatch.setenv("AI_GEMINI_API_KEY", "env-key")
        # Need fresh instance (bypass lru_cache)
        cfg = AISettings()
        assert cfg.gemini_api_key == "env-key"
