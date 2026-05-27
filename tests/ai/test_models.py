"""
test_models.py -- Tests for ai.models (Phase 4-H).

Run:
    PYTHONPATH=src:. pytest tests/ai/test_models.py -v
"""
from __future__ import annotations

from datetime import datetime

from ai.models import NarrativeResult, NarrativeSection


class TestNarrativeSection:
    def test_all_fields_default_to_empty_string(self):
        sec = NarrativeSection()
        assert sec.research_context == ""
        assert sec.risk_analysis == ""
        assert sec.consumer_summary == ""
        assert sec.formatted_html == ""

    def test_fields_settable(self):
        sec = NarrativeSection(
            research_context="ctx",
            risk_analysis="risk",
            consumer_summary="summary",
            formatted_html="<p>html</p>",
        )
        assert sec.research_context == "ctx"
        assert sec.risk_analysis == "risk"
        assert sec.consumer_summary == "summary"
        assert sec.formatted_html == "<p>html</p>"


class TestNarrativeResult:
    def test_fallback_defaults_false(self):
        r = NarrativeResult(npi="1234567890")
        assert r.fallback is False

    def test_errors_defaults_empty(self):
        r = NarrativeResult(npi="1234567890")
        assert r.errors == []

    def test_model_versions_defaults_empty(self):
        r = NarrativeResult(npi="1234567890")
        assert r.model_versions == {}

    def test_generated_at_is_datetime(self):
        r = NarrativeResult(npi="1234567890")
        assert isinstance(r.generated_at, datetime)

    def test_npi_preserved(self):
        r = NarrativeResult(npi="9876543210")
        assert r.npi == "9876543210"

    def test_sections_defaults_to_empty_section(self):
        r = NarrativeResult(npi="1234567890")
        assert isinstance(r.sections, NarrativeSection)
        assert r.sections.formatted_html == ""

    def test_to_serialisable_returns_dict(self):
        r = NarrativeResult(npi="1234567890")
        d = r.to_serialisable()
        assert isinstance(d, dict)
        assert d["npi"] == "1234567890"

    def test_to_serialisable_datetime_is_string(self):
        r = NarrativeResult(npi="1234567890")
        d = r.to_serialisable()
        assert isinstance(d["generated_at"], str)

    def test_json_round_trip(self):
        r = NarrativeResult(
            npi="1234567890",
            sections=NarrativeSection(risk_analysis="medium risk"),
            fallback=True,
            errors=["step 1 failed"],
        )
        data = r.to_serialisable()
        r2 = NarrativeResult.model_validate(data)
        assert r2.npi == r.npi
        assert r2.sections.risk_analysis == r.sections.risk_analysis
        assert r2.fallback is True
        assert r2.errors == ["step 1 failed"]
