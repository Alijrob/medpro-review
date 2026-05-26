"""
test_persist_activity.py -- Tests for persist_report_activity (Phase 2-I).

14 tests. Activity called directly as a plain Python function.
DB not configured in test env -- expects persisted=False path.
"""
from __future__ import annotations

import pytest

from workers.activities import persist_report_activity
from workers.models import PersistReportInput, PersistReportOutput, ProviderPipelineResult

from ._fixtures import NPI_ALICE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_complete_result() -> dict:
    return ProviderPipelineResult(
        npi=NPI_ALICE,
        report={"npi": NPI_ALICE, "is_partial": False, "has_active_exclusion": False},
        html="<!DOCTYPE html><html><body>report</body></html>",
        report_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        is_partial=False,
        pipeline_status="complete",
        sources_attempted=["F1", "F2"],
        sources_succeeded=["F1", "F2"],
        sources_failed=[],
    ).model_dump(mode="json")


def _make_failed_result() -> dict:
    return ProviderPipelineResult(
        npi=NPI_ALICE,
        report=None,
        html="",
        report_id=None,
        is_partial=True,
        pipeline_status="failed",
        sources_attempted=["F1"],
        sources_succeeded=[],
        sources_failed=["F1"],
        error_message="Connection refused",
    ).model_dump(mode="json")


def _make_no_data_result() -> dict:
    return ProviderPipelineResult(
        npi=NPI_ALICE,
        report=None,
        html="",
        report_id=None,
        is_partial=True,
        pipeline_status="no_data",
        sources_attempted=["F1"],
        sources_succeeded=[],
        sources_failed=["F1"],
        error_message="No raw records retrieved.",
    ).model_dump(mode="json")


_VALID_REPORT_ID = "12345678-1234-1234-1234-123456789012"


# ---------------------------------------------------------------------------
# Not-configured path (expected in test env -- no REPORT_DATABASE_URL set)
# ---------------------------------------------------------------------------


def test_returns_persist_report_output():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    assert isinstance(out, PersistReportOutput)


def test_not_configured_persisted_false():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    assert out.persisted is False


def test_not_configured_error_message_explains():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    assert out.error_message is not None
    msg = out.error_message.lower()
    assert "not configured" in msg or "database" in msg


def test_not_configured_does_not_raise():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    assert out is not None


# ---------------------------------------------------------------------------
# Edge cases -- all go through not-configured path first (safe in test env)
# ---------------------------------------------------------------------------


def test_empty_report_id_returns_not_persisted():
    inp = PersistReportInput(report_id="", pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    assert out.persisted is False


def test_invalid_uuid_report_id_returns_not_persisted():
    inp = PersistReportInput(report_id="not-a-uuid", pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    assert out.persisted is False


def test_with_failed_pipeline_status():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_failed_result())
    out = persist_report_activity(inp)
    # Not configured catches it first -- persisted=False, no raise
    assert isinstance(out, PersistReportOutput)
    assert out.persisted is False


def test_with_no_data_pipeline_status():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_no_data_result())
    out = persist_report_activity(inp)
    assert isinstance(out, PersistReportOutput)


def test_with_empty_pipeline_result():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result={})
    out = persist_report_activity(inp)
    assert out.persisted is False


# ---------------------------------------------------------------------------
# Output serialisation
# ---------------------------------------------------------------------------


def test_output_json_serialisable():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    json_str = out.model_dump_json()
    assert '"persisted"' in json_str


def test_output_roundtrip():
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=_make_complete_result())
    out = persist_report_activity(inp)
    data = out.model_dump(mode="json")
    out2 = PersistReportOutput.model_validate(data)
    assert out2.persisted == out.persisted


# ---------------------------------------------------------------------------
# Partial pipeline result
# ---------------------------------------------------------------------------


def test_with_partial_result():
    partial = ProviderPipelineResult(
        npi=NPI_ALICE,
        report={"npi": NPI_ALICE, "is_partial": True},
        html="",
        report_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        is_partial=True,
        pipeline_status="partial",
        sources_attempted=["F1", "F2"],
        sources_succeeded=["F1"],
        sources_failed=["F2"],
    ).model_dump(mode="json")
    inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=partial)
    out = persist_report_activity(inp)
    assert isinstance(out, PersistReportOutput)


def test_does_not_raise_on_any_valid_input():
    for result in [_make_complete_result(), _make_failed_result(), _make_no_data_result()]:
        inp = PersistReportInput(report_id=_VALID_REPORT_ID, pipeline_result=result)
        out = persist_report_activity(inp)
        assert isinstance(out, PersistReportOutput)
