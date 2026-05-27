"""
test_prompts.py -- Tests for ai.prompts (Phase 4-H).

Run:
    PYTHONPATH=src:. pytest tests/ai/test_prompts.py -v
"""
from __future__ import annotations

from ai.prompts import (
    build_analysis_prompt,
    build_format_prompt,
    build_research_prompt,
    parse_analysis_response,
)


class TestBuildResearchPrompt:
    def test_includes_npi(self):
        prompt = build_research_prompt("1234567890", {"npi": "1234567890", "name": "Dr. X"})
        assert "1234567890" in prompt

    def test_includes_profile_json(self):
        prompt = build_research_prompt("1234567890", {"specialty": "Cardiology"})
        assert "Cardiology" in prompt

    def test_is_string(self):
        prompt = build_research_prompt("1234567890", {})
        assert isinstance(prompt, str)

    def test_mentions_licensing(self):
        prompt = build_research_prompt("1234567890", {})
        assert "licens" in prompt.lower()

    def test_mentions_exclusions(self):
        prompt = build_research_prompt("1234567890", {})
        assert "exclusion" in prompt.lower()


class TestBuildAnalysisPrompt:
    def test_includes_research_context(self):
        prompt = build_analysis_prompt("Provider has 2 active licenses in MA and NY.")
        assert "Provider has 2 active licenses in MA and NY." in prompt

    def test_includes_risk_analysis_marker(self):
        prompt = build_analysis_prompt("context")
        assert "[RISK_ANALYSIS]" in prompt

    def test_includes_consumer_summary_marker(self):
        prompt = build_analysis_prompt("context")
        assert "[CONSUMER_SUMMARY]" in prompt

    def test_is_string(self):
        assert isinstance(build_analysis_prompt("ctx"), str)


class TestParseAnalysisResponse:
    def test_extracts_risk_analysis(self):
        text = "[RISK_ANALYSIS]\nRISK LEVEL: LOW\nAll good.\n[END_RISK_ANALYSIS]\n[CONSUMER_SUMMARY]\nOK.\n[END_CONSUMER_SUMMARY]"
        risk, _ = parse_analysis_response(text)
        assert "RISK LEVEL: LOW" in risk
        assert "All good." in risk

    def test_extracts_consumer_summary(self):
        text = "[RISK_ANALYSIS]\nstuff\n[END_RISK_ANALYSIS]\n[CONSUMER_SUMMARY]\nThis provider is excellent.\n[END_CONSUMER_SUMMARY]"
        _, summary = parse_analysis_response(text)
        assert "This provider is excellent." in summary

    def test_returns_empty_string_for_missing_markers(self):
        risk, summary = parse_analysis_response("no markers here")
        assert risk == ""
        assert summary == ""

    def test_returns_empty_when_only_risk_present(self):
        text = "[RISK_ANALYSIS]\nstuff\n[END_RISK_ANALYSIS]"
        risk, summary = parse_analysis_response(text)
        assert "stuff" in risk
        assert summary == ""

    def test_strips_whitespace_from_extracted_text(self):
        text = "[RISK_ANALYSIS]\n\n  RISK LEVEL: HIGH  \n\n[END_RISK_ANALYSIS]\n[CONSUMER_SUMMARY]\n\n  summary  \n\n[END_CONSUMER_SUMMARY]"
        risk, summary = parse_analysis_response(text)
        assert risk.startswith("RISK LEVEL")
        assert summary.startswith("summary")


class TestBuildFormatPrompt:
    def test_includes_risk_analysis_text(self):
        prompt = build_format_prompt("RISK LEVEL: LOW\nAll clear.", "Good doctor.")
        assert "RISK LEVEL: LOW" in prompt

    def test_includes_consumer_summary_text(self):
        prompt = build_format_prompt("risk stuff", "Dr. Smith is board certified.")
        assert "Dr. Smith is board certified." in prompt

    def test_mentions_html(self):
        prompt = build_format_prompt("risk", "summary")
        assert "HTML" in prompt or "html" in prompt.lower()

    def test_is_string(self):
        assert isinstance(build_format_prompt("r", "s"), str)
