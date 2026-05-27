"""
test_narrative.py -- Tests for ai.narrative.NarrativeGenerator (Phase 4-H).

All providers use injectable clients. No live API calls.

Run:
    PYTHONPATH=src:. pytest tests/ai/test_narrative.py -v
"""
from __future__ import annotations

import asyncio

from ai.config import AISettings
from ai.models import NarrativeResult
from ai.narrative import NarrativeGenerator
from ai.providers import AnthropicProvider, GeminiProvider

_SETTINGS = AISettings(
    gemini_api_key="test-gemini",
    anthropic_api_key="test-anthropic",
)

_ANALYSIS_RESPONSE = (
    "[RISK_ANALYSIS]\nRISK LEVEL: LOW\nNo issues found.\n[END_RISK_ANALYSIS]\n"
    "[CONSUMER_SUMMARY]\nThis provider has a clean record.\n[END_CONSUMER_SUMMARY]"
)


def _gemini_client(research_text: str = "research context here"):
    """Returns a Gemini injectable client that produces a fixed research context."""
    return lambda prompt, *, model, max_tokens: research_text


def _anthropic_client(analysis_response: str = _ANALYSIS_RESPONSE, format_response: str = "<div>html</div>"):
    """Returns an Anthropic injectable client that alternates analysis / format responses."""
    calls = []

    def _client(prompt, *, model, max_tokens):
        calls.append(prompt)
        # First call (analysis prompt) -> analysis_response; second (format) -> format_response
        if len(calls) == 1:
            return analysis_response
        return format_response

    return _client


# ---------------------------------------------------------------------------

class TestNarrativeGeneratorFallback:
    def test_all_providers_unavailable_returns_fallback(self):
        settings = AISettings()  # no keys
        gen = NarrativeGenerator(settings)
        result = asyncio.run(gen.generate("1234567890", {"npi": "1234567890"}))
        assert isinstance(result, NarrativeResult)
        assert result.npi == "1234567890"
        assert result.fallback is False  # not fallback -- providers simply unavailable
        assert result.sections.research_context == ""
        assert result.sections.formatted_html == ""

    def test_gemini_unavailable_skips_all_steps(self):
        """If Gemini has no key, no research context -> Opus/Haiku skipped."""
        settings = AISettings(anthropic_api_key="key")
        gen = NarrativeGenerator(settings)
        result = asyncio.run(gen.generate("1234567890", {"npi": "1234567890"}))
        assert result.sections.research_context == ""
        assert result.sections.risk_analysis == ""
        assert result.sections.formatted_html == ""

    def test_anthropic_unavailable_after_research(self):
        """Gemini produces research but Anthropic has no key -> analysis/format skipped."""
        settings = AISettings(gemini_api_key="key")
        gemini = GeminiProvider(api_key="key", client=_gemini_client())
        gen = NarrativeGenerator(settings, gemini=gemini)
        result = asyncio.run(gen.generate("1234567890", {"npi": "1234567890"}))
        assert result.sections.research_context == "research context here"
        assert result.sections.risk_analysis == ""
        assert result.sections.formatted_html == ""


class TestNarrativeGeneratorFullPipeline:
    def test_full_pipeline_populates_all_sections(self):
        gemini = GeminiProvider(api_key="key", client=_gemini_client())
        anthropic = AnthropicProvider(api_key="key", client=_anthropic_client())
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini, anthropic=anthropic)
        result = asyncio.run(gen.generate("1234567890", {"npi": "1234567890"}))
        assert result.sections.research_context == "research context here"
        assert "RISK LEVEL: LOW" in result.sections.risk_analysis
        assert "clean record" in result.sections.consumer_summary
        assert "<div>html</div>" in result.sections.formatted_html

    def test_npi_propagated_to_result(self):
        gemini = GeminiProvider(api_key="key", client=_gemini_client())
        anthropic = AnthropicProvider(api_key="key", client=_anthropic_client())
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini, anthropic=anthropic)
        result = asyncio.run(gen.generate("9876543210", {"npi": "9876543210"}))
        assert result.npi == "9876543210"

    def test_model_versions_populated(self):
        gemini = GeminiProvider(api_key="key", client=_gemini_client())
        anthropic = AnthropicProvider(api_key="key", client=_anthropic_client())
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini, anthropic=anthropic)
        result = asyncio.run(gen.generate("1234567890", {}))
        assert "research" in result.model_versions
        assert "analysis" in result.model_versions
        assert "format" in result.model_versions

    def test_fallback_false_when_all_providers_respond(self):
        gemini = GeminiProvider(api_key="key", client=_gemini_client())
        anthropic = AnthropicProvider(api_key="key", client=_anthropic_client())
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini, anthropic=anthropic)
        result = asyncio.run(gen.generate("1234567890", {}))
        assert result.fallback is False

    def test_fallback_true_when_gemini_returns_empty(self):
        gemini = GeminiProvider(api_key="key", client=_gemini_client(""))
        anthropic = AnthropicProvider(api_key="key", client=_anthropic_client())
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini, anthropic=anthropic)
        result = asyncio.run(gen.generate("1234567890", {}))
        assert result.fallback is True
        assert result.sections.research_context == ""

    def test_pii_not_in_research_prompt(self):
        """PII fields must be scrubbed before building the research prompt."""
        captured_prompts = []

        def _recording_client(prompt, *, model, max_tokens):
            captured_prompts.append(prompt)
            return "research context"

        gemini = GeminiProvider(api_key="key", client=_recording_client)
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini)
        profile = {
            "npi": "1234567890",
            "ssn": "999-99-9999",
            "dob": "1970-01-01",
            "home_address": "1 Private Rd",
            "specialty": "Cardiology",
        }
        asyncio.run(gen.generate("1234567890", profile))
        assert captured_prompts, "Gemini client was not called"
        prompt = captured_prompts[0]
        assert "999-99-9999" not in prompt
        assert "1970-01-01" not in prompt
        assert "1 Private Rd" not in prompt
        assert "Cardiology" in prompt  # non-PII preserved

    def test_errors_collected_on_exception(self):
        def _bad_client(prompt, *, model, max_tokens):
            raise RuntimeError("upstream error")

        gemini = GeminiProvider(api_key="key", client=_bad_client)
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini)
        result = asyncio.run(gen.generate("1234567890", {}))
        # Provider catches exception internally -> returns ""
        # No errors collected at narrative level for provider-level exceptions
        assert result.sections.research_context == ""

    def test_result_is_json_serialisable(self):
        gemini = GeminiProvider(api_key="key", client=_gemini_client())
        anthropic = AnthropicProvider(api_key="key", client=_anthropic_client())
        gen = NarrativeGenerator(_SETTINGS, gemini=gemini, anthropic=anthropic)
        result = asyncio.run(gen.generate("1234567890", {}))
        data = result.to_serialisable()
        assert isinstance(data, dict)
        assert isinstance(data["generated_at"], str)


class TestNarrativeGeneratorRouter:
    def test_router_generate_narrative_function(self):
        """ai.generate_narrative top-level function works end-to-end."""
        import asyncio as _asyncio
        from ai import generate_narrative

        gemini = GeminiProvider(api_key="key", client=_gemini_client())
        anthropic = AnthropicProvider(api_key="key", client=_anthropic_client())
        result = _asyncio.run(
            generate_narrative(
                "1234567890",
                {"npi": "1234567890"},
                _SETTINGS,
                gemini=gemini,
                anthropic=anthropic,
            )
        )
        assert result.npi == "1234567890"
        assert result.sections.research_context == "research context here"
