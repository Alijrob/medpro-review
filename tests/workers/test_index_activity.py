"""
test_index_activity.py -- Tests for index_profile_activity (C14 wrapper).

14 tests. Activities called directly as plain Python functions.
OpenSearch not configured in test env -- expects is_configured=False path.
"""
from __future__ import annotations

import pytest

from workers.activities import index_profile_activity
from workers.models import IndexProfileInput, IndexProfileOutput

from ._fixtures import NPI_ALICE, _make_full_profile, _make_minimal_profile


def _profile_dict(npi: str = NPI_ALICE) -> dict:
    return _make_full_profile().model_dump(mode="json")


def _minimal_profile_dict() -> dict:
    return _make_minimal_profile().model_dump(mode="json")


# ---------------------------------------------------------------------------
# Not-configured path (expected in test env)
# ---------------------------------------------------------------------------


def test_returns_index_profile_output():
    inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
    out = index_profile_activity(inp)
    assert isinstance(out, IndexProfileOutput)


def test_not_configured_returns_indexed_false():
    """OpenSearch not configured or unreachable -- should return indexed=False, not raise."""
    inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
    out = index_profile_activity(inp)
    # In test env, OpenSearch is either not configured or not running
    assert out.indexed is False


def test_not_configured_doc_id_is_none():
    inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
    out = index_profile_activity(inp)
    assert out.doc_id is None


def test_not_configured_error_message_explains():
    """OpenSearch is either not configured or unreachable -- error_message must explain."""
    inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
    out = index_profile_activity(inp)
    assert out.error_message is not None
    # Either "not configured" (no URL set) or a connection error (URL set but no server)
    msg = out.error_message.lower()
    assert (
        "not configured" in msg
        or "opensearch" in msg
        or "connection" in msg
        or "index failed" in msg
        or "errno" in msg
    )


def test_not_configured_does_not_raise():
    """Must return gracefully -- never raise on missing config."""
    inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
    # No exception expected
    out = index_profile_activity(inp)
    assert out is not None


# ---------------------------------------------------------------------------
# Invalid profile
# ---------------------------------------------------------------------------


def test_invalid_profile_returns_not_indexed():
    inp = IndexProfileInput(profile={"garbage": True}, npi=NPI_ALICE)
    out = index_profile_activity(inp)
    # Either not-configured path catches it first, or profile validation fails
    assert out.indexed is False


def test_empty_profile_returns_not_indexed():
    inp = IndexProfileInput(profile={}, npi=NPI_ALICE)
    out = index_profile_activity(inp)
    assert out.indexed is False


# ---------------------------------------------------------------------------
# Output JSON-serialisable
# ---------------------------------------------------------------------------


def test_output_json_serialisable():
    inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
    out = index_profile_activity(inp)
    json_str = out.model_dump_json()
    assert '"indexed"' in json_str


def test_output_roundtrip():
    inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
    out = index_profile_activity(inp)
    data = out.model_dump(mode="json")
    out2 = IndexProfileOutput.model_validate(data)
    assert out2.indexed == out.indexed


# ---------------------------------------------------------------------------
# Minimal profile
# ---------------------------------------------------------------------------


def test_minimal_profile_not_indexed_in_dev():
    inp = IndexProfileInput(profile=_minimal_profile_dict(), npi=NPI_ALICE)
    out = index_profile_activity(inp)
    assert out.indexed is False


# ---------------------------------------------------------------------------
# NPI in input
# ---------------------------------------------------------------------------


def test_npi_in_input_accepted():
    inp = IndexProfileInput(profile=_profile_dict(), npi="9876543210")
    out = index_profile_activity(inp)
    assert isinstance(out, IndexProfileOutput)


# ---------------------------------------------------------------------------
# Configured path (mock -- set env var then reset)
# ---------------------------------------------------------------------------


def test_configured_with_unreachable_host_returns_not_indexed(monkeypatch):
    """With SEARCH_OPENSEARCH_URL set but unreachable, should return indexed=False."""
    monkeypatch.setenv("SEARCH_OPENSEARCH_URL", "http://localhost:29200")
    # Clear lru_cache to pick up new env
    from search.config import get_settings
    get_settings.cache_clear()
    try:
        inp = IndexProfileInput(profile=_profile_dict(), npi=NPI_ALICE)
        out = index_profile_activity(inp)
        # Should fail gracefully (connection refused), not raise
        assert out.indexed is False
    finally:
        monkeypatch.delenv("SEARCH_OPENSEARCH_URL", raising=False)
        get_settings.cache_clear()
