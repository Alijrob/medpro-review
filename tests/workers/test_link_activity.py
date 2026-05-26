"""
test_link_activity.py -- Tests for link_and_merge_activity (C13 wrapper).

16 tests. Activities called directly as plain Python functions.
Builds UnifiedIdBundle + NormalizedRecord inputs via lower-level helpers.
"""
from __future__ import annotations

import pytest

from workers.activities import (
    normalize_records_activity,
    resolve_identity_activity,
    link_and_merge_activity,
)
from workers.models import (
    NormalizeRecordsInput,
    ResolveIdentityInput,
    LinkAndMergeInput,
    LinkAndMergeOutput,
)

from ._fixtures import NPI_ALICE

_NPPES_RAW_DICT = {
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


def _pipeline_to_bundle(npi: str = NPI_ALICE):
    """Run fetch -> normalize -> resolve to get a bundle dict."""
    from connectors.models import RawRecord
    raw_dict = RawRecord.from_raw("F1", {**_NPPES_RAW_DICT, "number": npi}).model_dump(mode="json")
    norm_out = normalize_records_activity(
        NormalizeRecordsInput(raw_records=[raw_dict], entity_npi=npi)
    )
    resolve_out = resolve_identity_activity(
        ResolveIdentityInput(npi=npi, normalized_records=norm_out.normalized_records)
    )
    return resolve_out.bundle, norm_out.normalized_records


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_link_and_merge_output():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert isinstance(out, LinkAndMergeOutput)


def test_profile_is_dict():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert isinstance(out.profile, dict)


def test_profile_has_npi():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert out.profile["npi"] == NPI_ALICE


def test_profile_has_entity_type():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert "entity_type" in out.profile


def test_profile_has_primary_name():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert "primary_name" in out.profile


# ---------------------------------------------------------------------------
# Completeness score
# ---------------------------------------------------------------------------


def test_completeness_score_is_float():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert isinstance(out.completeness_score, float)


def test_completeness_score_in_range():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert 0.0 <= out.completeness_score <= 1.0


# ---------------------------------------------------------------------------
# is_partial flag
# ---------------------------------------------------------------------------


def test_profile_has_is_partial_field():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert "is_partial" in out.profile


# ---------------------------------------------------------------------------
# Empty records (minimal merge)
# ---------------------------------------------------------------------------


def test_empty_records_still_produces_profile():
    """Bundle with no NormalizedRecords should still produce a minimal profile."""
    bundle, _ = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=[], npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert out.profile["npi"] == NPI_ALICE


def test_empty_records_low_completeness():
    bundle, _ = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=[], npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    # With no data records, completeness should be low
    assert out.completeness_score <= 0.5


# ---------------------------------------------------------------------------
# Invalid bundle raises
# ---------------------------------------------------------------------------


def test_invalid_bundle_raises():
    inp = LinkAndMergeInput(bundle={"garbage": True}, normalized_records=[], npi=NPI_ALICE)
    with pytest.raises(Exception):
        link_and_merge_activity(inp)


# ---------------------------------------------------------------------------
# Output JSON-serialisable
# ---------------------------------------------------------------------------


def test_output_json_serialisable():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    json_str = out.model_dump_json()
    assert '"profile"' in json_str


def test_output_roundtrip():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    data = out.model_dump(mode="json")
    out2 = LinkAndMergeOutput.model_validate(data)
    assert out2.profile["npi"] == out.profile["npi"]


# ---------------------------------------------------------------------------
# Invalid normalized records skipped gracefully
# ---------------------------------------------------------------------------


def test_invalid_normalized_records_skipped():
    bundle, records = _pipeline_to_bundle()
    bad_records = records + [{"garbage": True}]
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=bad_records, npi=NPI_ALICE)
    # Should not raise; invalid records are logged and skipped
    out = link_and_merge_activity(inp)
    assert out.profile["npi"] == NPI_ALICE


def test_profile_schema_version_v1():
    bundle, records = _pipeline_to_bundle()
    inp = LinkAndMergeInput(bundle=bundle, normalized_records=records, npi=NPI_ALICE)
    out = link_and_merge_activity(inp)
    assert out.profile.get("schema_version") == "v1"
