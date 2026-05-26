"""
test_fetch_activity.py -- Tests for fetch_source_activity (C10 connector wrapper).

14 tests. The activity is async; tests use pytest-asyncio.
In dev/test env (no live credentials), all sources return fetch_status="failed"
or fetch_status="success" with empty records (legal gate).
"""
from __future__ import annotations

import pytest

from workers.models import FetchSourceInput, FetchSourceOutput


# ---------------------------------------------------------------------------
# Helper: call the async activity directly in tests
# ---------------------------------------------------------------------------

async def _fetch(npi: str, source_id: str) -> FetchSourceOutput:
    from workers.activities import fetch_source_activity
    return await fetch_source_activity(FetchSourceInput(npi=npi, source_id=source_id))


NPI = "1234567890"


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_fetch_source_output():
    out = await _fetch(NPI, "F1")
    assert isinstance(out, FetchSourceOutput)


@pytest.mark.asyncio
async def test_source_id_echoed():
    out = await _fetch(NPI, "F1")
    assert out.source_id == "F1"


@pytest.mark.asyncio
async def test_fetch_status_is_string():
    out = await _fetch(NPI, "F1")
    assert isinstance(out.fetch_status, str)
    assert out.fetch_status in ("success", "partial", "failed")


@pytest.mark.asyncio
async def test_raw_records_is_list():
    out = await _fetch(NPI, "F1")
    assert isinstance(out.raw_records, list)


# ---------------------------------------------------------------------------
# Unknown source_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_source_id_returns_failed():
    out = await _fetch(NPI, "UNKNOWN")
    assert out.fetch_status == "failed"
    assert out.error_message is not None


@pytest.mark.asyncio
async def test_unknown_source_id_returns_empty_records():
    out = await _fetch(NPI, "UNKNOWN")
    assert out.raw_records == []


# ---------------------------------------------------------------------------
# I4 (taxonomy crosswalk -- static, no fetch needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_i4_returns_success_empty_records():
    """I4 is a static crosswalk -- no network call, always succeeds with empty records."""
    out = await _fetch(NPI, "I4")
    assert out.fetch_status == "success"
    assert out.raw_records == []
    assert out.records_count == 0


# ---------------------------------------------------------------------------
# All P1 sources: confirm they return without raising
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_f1_does_not_raise():
    out = await _fetch(NPI, "F1")
    assert out is not None


@pytest.mark.asyncio
async def test_f2_does_not_raise():
    out = await _fetch(NPI, "F2")
    assert out is not None


@pytest.mark.asyncio
async def test_f3_does_not_raise():
    out = await _fetch(NPI, "F3")
    assert out is not None


@pytest.mark.asyncio
async def test_i1_does_not_raise():
    out = await _fetch(NPI, "I1")
    assert out is not None


@pytest.mark.asyncio
async def test_a1_does_not_raise():
    out = await _fetch(NPI, "A1")
    assert out is not None


# ---------------------------------------------------------------------------
# Output JSON-serialisable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_json_serialisable():
    out = await _fetch(NPI, "F1")
    json_str = out.model_dump_json()
    assert '"source_id"' in json_str
    assert '"fetch_status"' in json_str


@pytest.mark.asyncio
async def test_output_roundtrip():
    out = await _fetch(NPI, "I4")  # I4 is deterministic
    data = out.model_dump(mode="json")
    out2 = FetchSourceOutput.model_validate(data)
    assert out2.source_id == out.source_id
    assert out2.fetch_status == out.fetch_status
