"""
test_resolve_activity.py -- Tests for resolve_identity_activity (C12 wrapper).

16 tests. Activities called directly as plain Python functions.
"""
from __future__ import annotations

import pytest

from workers.activities import normalize_records_activity, resolve_identity_activity
from workers.models import (
    NormalizeRecordsInput,
    ResolveIdentityInput,
    ResolveIdentityOutput,
)

from ._fixtures import NPI_ALICE

# NPPES raw record that normalizes correctly
_NPPES_RAW_DICT_TMPL = {
    "number": NPI_ALICE,
    "enumeration_type": "NPI-1",
    "basic": {
        "first_name": "Alice",
        "last_name": "Smith",
        "gender": "F",
        "credential": "MD",
        "status": "A",
    },
    "addresses": [
        {
            "address_1": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "postal_code": "90001",
            "address_purpose": "LOCATION",
        }
    ],
    "taxonomies": [
        {"code": "207Q00000X", "desc": "Family Medicine", "primary": True}
    ],
}


def _make_normalized_records(npi: str = NPI_ALICE) -> list[dict]:
    """Build normalized record dicts via the normalize activity."""
    from connectors.models import RawRecord
    raw_dict = RawRecord.from_raw("F1", {**_NPPES_RAW_DICT_TMPL, "number": npi}).model_dump(mode="json")
    out = normalize_records_activity(
        NormalizeRecordsInput(raw_records=[raw_dict], entity_npi=npi)
    )
    return out.normalized_records


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_resolve_identity_output():
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=[])
    out = resolve_identity_activity(inp)
    assert isinstance(out, ResolveIdentityOutput)


def test_empty_records_returns_no_records_status():
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=[])
    out = resolve_identity_activity(inp)
    assert out.resolution_status == "no_records"
    assert out.bundle is None
    assert out.confidence == 0.0


# ---------------------------------------------------------------------------
# Successful resolution
# ---------------------------------------------------------------------------


def test_resolves_with_f1_record():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    assert out.resolution_status == "resolved"


def test_bundle_not_none_on_success():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    assert out.bundle is not None


def test_bundle_is_dict():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    assert isinstance(out.bundle, dict)


def test_bundle_has_primary_npi():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    assert out.bundle["primary_npi"] == NPI_ALICE


def test_confidence_is_positive_on_success():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    assert out.confidence > 0.0


def test_source_ids_contributing_includes_f1():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    assert "F1" in out.source_ids_contributing


# ---------------------------------------------------------------------------
# Invalid records (graceful degradation)
# ---------------------------------------------------------------------------


def test_all_invalid_records_returns_failed():
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=[{"garbage": True}])
    out = resolve_identity_activity(inp)
    assert out.resolution_status == "failed"
    assert out.bundle is None


def test_mixed_valid_invalid_resolves():
    """One valid + one invalid record -- resolver should still succeed."""
    records = _make_normalized_records(NPI_ALICE)
    records.append({"garbage": True})
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    assert out.resolution_status == "resolved"


# ---------------------------------------------------------------------------
# Output JSON-serialisable
# ---------------------------------------------------------------------------


def test_output_json_serialisable():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    json_str = out.model_dump_json()
    assert '"resolution_status"' in json_str


def test_output_roundtrip():
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=records)
    out = resolve_identity_activity(inp)
    data = out.model_dump(mode="json")
    out2 = ResolveIdentityOutput.model_validate(data)
    assert out2.resolution_status == out.resolution_status


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_npi_mismatch_does_not_crash():
    """NPI in records differs from inp.npi -- resolver may not find the bundle."""
    records = _make_normalized_records(NPI_ALICE)
    inp = ResolveIdentityInput(npi="9999999999", normalized_records=records)
    out = resolve_identity_activity(inp)
    # Should not raise; bundle may be None if npi lookup misses
    assert isinstance(out, ResolveIdentityOutput)


def test_confidence_is_zero_when_empty():
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=[])
    out = resolve_identity_activity(inp)
    assert out.confidence == 0.0


def test_source_ids_empty_when_no_records():
    inp = ResolveIdentityInput(npi=NPI_ALICE, normalized_records=[])
    out = resolve_identity_activity(inp)
    assert out.source_ids_contributing == []
