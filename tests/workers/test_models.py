"""
test_models.py -- Tests for worker Pydantic I/O models.

Covers all models added across Phase 2-H and Phase 2-I.
"""
from __future__ import annotations

from workers.models import (
    FetchSourceInput,
    FetchSourceOutput,
    GenerateReportInput,
    GenerateReportOutput,
    IndexProfileInput,
    IndexProfileOutput,
    LinkAndMergeInput,
    LinkAndMergeOutput,
    NormalizeRecordsInput,
    NormalizeRecordsOutput,
    PersistReportInput,
    PersistReportOutput,
    ProviderPipelineInput,
    ProviderPipelineResult,
    ResolveIdentityInput,
    ResolveIdentityOutput,
)

from ._fixtures import NPI_ALICE

_VALID_UUID = "12345678-1234-1234-1234-123456789012"


# ---------------------------------------------------------------------------
# PersistReportInput (Phase 2-I)
# ---------------------------------------------------------------------------


def test_persist_report_input_instantiation():
    inp = PersistReportInput(
        report_id=_VALID_UUID,
        pipeline_result={"npi": NPI_ALICE, "pipeline_status": "complete"},
    )
    assert inp.report_id == _VALID_UUID
    assert inp.pipeline_result["npi"] == NPI_ALICE


def test_persist_report_input_empty_report_id_allowed():
    """Empty string is allowed -- activity handles the guard internally."""
    inp = PersistReportInput(report_id="", pipeline_result={})
    assert inp.report_id == ""


def test_persist_report_input_json_serialisable():
    inp = PersistReportInput(report_id=_VALID_UUID, pipeline_result={"k": "v"})
    j = inp.model_dump_json()
    assert '"report_id"' in j
    assert '"pipeline_result"' in j


def test_persist_report_input_roundtrip():
    inp = PersistReportInput(report_id=_VALID_UUID, pipeline_result={"x": 1})
    data = inp.model_dump(mode="json")
    inp2 = PersistReportInput.model_validate(data)
    assert inp2.report_id == inp.report_id
    assert inp2.pipeline_result == inp.pipeline_result


# ---------------------------------------------------------------------------
# PersistReportOutput (Phase 2-I)
# ---------------------------------------------------------------------------


def test_persist_report_output_defaults():
    out = PersistReportOutput()
    assert out.persisted is False
    assert out.error_message is None


def test_persist_report_output_persisted_true():
    out = PersistReportOutput(persisted=True)
    assert out.persisted is True


def test_persist_report_output_with_error():
    out = PersistReportOutput(persisted=False, error_message="DB not configured")
    assert out.error_message == "DB not configured"


def test_persist_report_output_json_serialisable():
    out = PersistReportOutput(persisted=False, error_message="err")
    j = out.model_dump_json()
    assert '"persisted"' in j
    assert '"error_message"' in j


def test_persist_report_output_roundtrip():
    out = PersistReportOutput(persisted=True)
    data = out.model_dump(mode="json")
    out2 = PersistReportOutput.model_validate(data)
    assert out2.persisted == out.persisted


# ---------------------------------------------------------------------------
# ProviderPipelineInput.report_id (Phase 2-I addition)
# ---------------------------------------------------------------------------


def test_pipeline_input_report_id_defaults_to_none():
    inp = ProviderPipelineInput(npi=NPI_ALICE)
    assert inp.report_id is None


def test_pipeline_input_with_report_id():
    inp = ProviderPipelineInput(npi=NPI_ALICE, report_id=_VALID_UUID)
    assert inp.report_id == _VALID_UUID


def test_pipeline_input_backward_compat_no_report_id():
    """Existing code that doesn't supply report_id must still work."""
    inp = ProviderPipelineInput(npi=NPI_ALICE, source_ids=["F1", "F2"], include_html=True)
    assert inp.report_id is None
    assert inp.npi == NPI_ALICE


# ---------------------------------------------------------------------------
# Smoke tests for other Phase 2-H models
# ---------------------------------------------------------------------------


def test_fetch_source_input():
    inp = FetchSourceInput(npi=NPI_ALICE, source_id="F1")
    assert inp.source_id == "F1"


def test_fetch_source_output_defaults():
    out = FetchSourceOutput(source_id="F1", fetch_status="success")
    assert out.raw_records == []
    assert out.records_count == 0


def test_normalize_records_output_defaults():
    out = NormalizeRecordsOutput()
    assert out.normalized_records == []
    assert out.normalization_errors == []


def test_resolve_identity_output_defaults():
    out = ResolveIdentityOutput(resolution_status="no_records")
    assert out.bundle is None
    assert out.confidence == 0.0


def test_index_profile_output_defaults():
    out = IndexProfileOutput()
    assert out.indexed is False
    assert out.doc_id is None


def test_generate_report_output_defaults():
    out = GenerateReportOutput(report={"npi": NPI_ALICE})
    assert out.html == ""
    assert out.report_id == ""


def test_pipeline_result_json_roundtrip():
    result = ProviderPipelineResult(
        npi=NPI_ALICE,
        pipeline_status="complete",
        sources_attempted=["F1"],
        sources_succeeded=["F1"],
        sources_failed=[],
        report={"npi": NPI_ALICE},
        report_id=_VALID_UUID,
        is_partial=False,
    )
    data = result.model_dump(mode="json")
    result2 = ProviderPipelineResult.model_validate(data)
    assert result2.pipeline_status == "complete"
    assert result2.report_id == _VALID_UUID
