"""
test_generate_report_activity.py -- Tests for generate_report_activity (C17 wrapper).

16 tests. Activities called directly as plain Python functions.
"""
from __future__ import annotations

import pytest

from workers.activities import generate_report_activity
from workers.models import GenerateReportInput, GenerateReportOutput

from ._fixtures import NPI_ALICE, _make_full_profile, _make_minimal_profile


def _full_profile():
    return _make_full_profile()


def _minimal_profile():
    return _make_minimal_profile()


# ---------------------------------------------------------------------------
# Extended profiles needed for this test file
# ---------------------------------------------------------------------------

def _excluded_profile():
    from datetime import date
    from schema.v1.profile import ExclusionRecord
    p = _make_full_profile()
    return p.model_copy(update={
        "currently_excluded": True,
        "exclusions": [
            ExclusionRecord(
                source_registry="OIG LEIE",
                exclusion_type="Mandatory",
                exclusion_date=date(2022, 3, 15),
                is_active=True,
                source_id="F2",
            ),
        ],
    })


def _partial_profile():
    from datetime import datetime, timezone
    from uuid import UUID
    from schema.v1.common import EntityType, ProviderName
    from schema.v1.profile import CanonicalProviderProfile
    return CanonicalProviderProfile(
        npi="6666666666",
        bundle_id=UUID("11111111-1111-1111-1111-111111111111"),
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Frank", last="Grant"),
        is_partial=True,
        sources_attempted=["F1", "F2", "F3"],
        sources_succeeded=["F1"],
        sources_failed=["F2", "F3"],
        overall_confidence=0.50,
        report_completeness_score=0.30,
        created_at=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
    )


def _inp(profile_dict: dict, include_html: bool = True) -> GenerateReportInput:
    return GenerateReportInput(profile=profile_dict, npi=NPI_ALICE, include_html=include_html)


def _full_profile_dict() -> dict:
    return _full_profile().model_dump(mode="json")


def _minimal_profile_dict() -> dict:
    return _minimal_profile().model_dump(mode="json")


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_generate_report_output():
    out = generate_report_activity(_inp(_full_profile_dict()))
    assert isinstance(out, GenerateReportOutput)


def test_report_is_dict():
    out = generate_report_activity(_inp(_full_profile_dict()))
    assert isinstance(out.report, dict)


def test_report_id_is_string():
    out = generate_report_activity(_inp(_full_profile_dict()))
    assert isinstance(out.report_id, str)
    assert len(out.report_id) > 0


def test_report_has_npi():
    out = generate_report_activity(_inp(_full_profile_dict()))
    assert out.report["npi"] == NPI_ALICE


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------


def test_html_generated_when_include_html_true():
    out = generate_report_activity(_inp(_full_profile_dict(), include_html=True))
    assert len(out.html) > 100
    assert "<!DOCTYPE html>" in out.html


def test_html_empty_when_include_html_false():
    out = generate_report_activity(_inp(_full_profile_dict(), include_html=False))
    assert out.html == ""


def test_html_contains_provider_name():
    out = generate_report_activity(_inp(_full_profile_dict(), include_html=True))
    assert "Alice" in out.html


def test_html_contains_disclaimer():
    out = generate_report_activity(_inp(_full_profile_dict(), include_html=True))
    assert "IMPORTANT NOTICE" in out.html


# ---------------------------------------------------------------------------
# Partial profile
# ---------------------------------------------------------------------------


def test_partial_profile_report_is_partial():
    out = generate_report_activity(_inp(_partial_profile().model_dump(mode="json")))
    assert out.report["is_partial"] is True


def test_full_profile_report_not_partial():
    out = generate_report_activity(_inp(_full_profile_dict()))
    assert out.report["is_partial"] is False


# ---------------------------------------------------------------------------
# Exclusion flag in report
# ---------------------------------------------------------------------------


def test_excluded_profile_report_has_active_exclusion():
    profile_dict = _excluded_profile().model_dump(mode="json")
    out = generate_report_activity(_inp(profile_dict))
    assert out.report["has_active_exclusion"] is True


def test_clean_profile_report_no_active_exclusion():
    out = generate_report_activity(_inp(_full_profile_dict()))
    assert out.report["has_active_exclusion"] is False


# ---------------------------------------------------------------------------
# Invalid profile raises
# ---------------------------------------------------------------------------


def test_invalid_profile_raises():
    inp = GenerateReportInput(profile={"garbage": True}, npi=NPI_ALICE)
    with pytest.raises(Exception):
        generate_report_activity(inp)


# ---------------------------------------------------------------------------
# Output JSON-serialisable
# ---------------------------------------------------------------------------


def test_output_json_serialisable():
    out = generate_report_activity(_inp(_full_profile_dict()))
    json_str = out.model_dump_json()
    assert '"report"' in json_str
    assert '"report_id"' in json_str


def test_output_roundtrip():
    out = generate_report_activity(_inp(_full_profile_dict()))
    data = out.model_dump(mode="json")
    out2 = GenerateReportOutput.model_validate(data)
    assert out2.report_id == out.report_id


# ---------------------------------------------------------------------------
# Minimal profile
# ---------------------------------------------------------------------------


def test_minimal_profile_generates_report():
    out = generate_report_activity(_inp(_minimal_profile_dict()))
    assert out.report["npi"] == NPI_ALICE
    assert out.report_id is not None
