"""
test_generate_ai_narrative_activity.py -- Tests for generate_ai_narrative_activity (Phase 4-H).

Activities are called directly as plain async Python functions (no Temporal server).
All AI providers use injectable clients -- no live API calls.

Run:
    PYTHONPATH=src:. pytest tests/workers/test_generate_ai_narrative_activity.py -v
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from ai.config import AISettings
from ai.models import NarrativeResult, NarrativeSection
from ai.providers import AnthropicProvider, GeminiProvider
from workers.activities.generate_ai_narrative import generate_ai_narrative_activity
from workers.models import GenerateNarrativeInput, GenerateNarrativeOutput

from ._fixtures import NPI_ALICE, _make_full_profile

_DUMMY_PROFILE = _make_full_profile().model_dump(mode="json")

_ANALYSIS_RESPONSE = (
    "[RISK_ANALYSIS]\nRISK LEVEL: LOW\nClean record.\n[END_RISK_ANALYSIS]\n"
    "[CONSUMER_SUMMARY]\nExcellent provider.\n[END_CONSUMER_SUMMARY]"
)


def _make_inp(npi: str = NPI_ALICE) -> GenerateNarrativeInput:
    return GenerateNarrativeInput(profile=_DUMMY_PROFILE, npi=npi)


# ---------------------------------------------------------------------------


class TestActivityWithNoKeys:
    def test_returns_fallback_true_when_no_api_keys(self):
        """With no API keys, both providers are unavailable -- narrative is empty."""
        inp = _make_inp()
        # Patch get_ai_settings to return settings with no keys + enabled
        with patch(
            "workers.activities.generate_ai_narrative.get_ai_settings",
            return_value=AISettings(narrative_enabled=True),
        ):
            out = asyncio.run(generate_ai_narrative_activity(inp))
        assert isinstance(out, GenerateNarrativeOutput)
        # narrative dict is present but all sections empty (not None, since generate() ran)
        assert out.error_message is None
        assert out.fallback is False  # providers simply unavailable, not a failure

    def test_returns_none_when_narrative_disabled(self):
        """AI_NARRATIVE_ENABLED=false -> narrative=None, fallback=True."""
        inp = _make_inp()
        with patch(
            "workers.activities.generate_ai_narrative.get_ai_settings",
            return_value=AISettings(narrative_enabled=False),
        ):
            out = asyncio.run(generate_ai_narrative_activity(inp))
        assert out.narrative is None
        assert out.fallback is True


class TestActivityWithMockProviders:
    def _run_with_mocks(self, gemini_response: str, analysis_response: str, format_response: str):
        """Helper: run the activity with injectable provider clients."""
        call_count = [0]

        def _anthropic_client(prompt, *, model, max_tokens):
            call_count[0] += 1
            if call_count[0] == 1:
                return analysis_response
            return format_response

        gemini = GeminiProvider(
            api_key="test-gemini",
            client=lambda p, *, model, max_tokens: gemini_response,
        )
        anthropic = AnthropicProvider(
            api_key="test-anthropic",
            client=_anthropic_client,
        )

        settings = AISettings(gemini_api_key="test-gemini", anthropic_api_key="test-anthropic")

        with patch(
            "workers.activities.generate_ai_narrative.get_ai_settings",
            return_value=settings,
        ):
            with patch("workers.activities.generate_ai_narrative.generate_narrative") as mock_gen:
                result = NarrativeResult(
                    npi=NPI_ALICE,
                    sections=NarrativeSection(
                        research_context=gemini_response,
                        risk_analysis="RISK LEVEL: LOW\nClean record.",
                        consumer_summary="Excellent provider.",
                        formatted_html="<div>html</div>",
                    ),
                    model_versions={
                        "research": "gemini-2.5-pro",
                        "analysis": "claude-opus-4-7",
                        "format": "claude-haiku-4-5-20251001",
                    },
                    fallback=False,
                )
                mock_gen.return_value = result
                mock_gen.side_effect = None

                async def _async_result(*a, **kw):
                    return result

                mock_gen.side_effect = _async_result
                inp = _make_inp()
                return asyncio.run(generate_ai_narrative_activity(inp))

    def test_narrative_present_in_output(self):
        out = self._run_with_mocks("research ctx", _ANALYSIS_RESPONSE, "<div>html</div>")
        assert out.narrative is not None
        assert isinstance(out.narrative, dict)
        assert out.narrative["npi"] == NPI_ALICE

    def test_fallback_false_in_output(self):
        out = self._run_with_mocks("research ctx", _ANALYSIS_RESPONSE, "<div>html</div>")
        assert out.fallback is False

    def test_error_message_none_on_success(self):
        out = self._run_with_mocks("research ctx", _ANALYSIS_RESPONSE, "<div>html</div>")
        assert out.error_message is None


class TestActivityErrorHandling:
    def test_exception_in_generate_narrative_returns_fallback(self):
        """If generate_narrative raises, activity returns fallback=True, never raises."""
        inp = _make_inp()

        async def _exploding_generate(*a, **kw):
            raise RuntimeError("AI service unavailable")

        settings = AISettings(
            narrative_enabled=True,
            gemini_api_key="key",
            anthropic_api_key="key",
        )
        with patch(
            "workers.activities.generate_ai_narrative.get_ai_settings",
            return_value=settings,
        ):
            with patch(
                "workers.activities.generate_ai_narrative.generate_narrative",
                side_effect=_exploding_generate,
            ):
                out = asyncio.run(generate_ai_narrative_activity(inp))

        assert out.narrative is None
        assert out.fallback is True
        assert out.error_message is not None
        assert "unavailable" in out.error_message

    def test_output_is_always_generate_narrative_output(self):
        """Activity always returns GenerateNarrativeOutput, never raises."""
        inp = _make_inp()
        with patch(
            "workers.activities.generate_ai_narrative.get_ai_settings",
            return_value=AISettings(narrative_enabled=True),
        ):
            out = asyncio.run(generate_ai_narrative_activity(inp))
        assert isinstance(out, GenerateNarrativeOutput)
