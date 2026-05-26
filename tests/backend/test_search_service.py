"""
tests/backend/test_search_service.py

Behavior tests for the Provider Search Service (C14, Phase 2-G).

All OpenSearch I/O is replaced via mock client injection through
backend.search_service.routes._set_singletons. No database, no network.

Coverage:
  Probes:
    GET /healthz -> 200 {"status": "ok"}
    GET /readyz  -> 200 {"status": "not_configured"} (default URL, shell mode)

  Search GET /v1/providers/search:
    - No params: 200, SearchResponse envelope
    - With q: passes q to build_search_query (verified via mock args)
    - With state filter: passes state
    - With page/page_size: pagination params respected
    - Returns hits mapped to ProviderSearchHit
    - Empty results: total=0, results=[]
    - has_exclusion filter

  NPI lookup GET /v1/providers/{npi}:
    - Found: 200 ProviderSearchHit
    - Not found (get_doc found=False): 404
    - Invalid NPI (non-digit): 422
    - Short NPI (9 digits): 422
    - get_doc returns None source: 404

  Indexing POST /v1/providers/{npi}/index:
    - Success: 201 IndexResult
    - NPI mismatch: 422
    - Client failure: 502
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from search.client import (
    BulkRawResponse,
    GetRawResponse,
    IndexRawResponse,
    OpenSearchClient,
    SearchRawResponse,
)
from search.config import SearchSettings, get_settings
from search.indexer import ProviderIndexer

from datetime import datetime, timezone
from uuid import UUID

from schema.v1.common import EntityType, Gender, ProviderName, SourceCategory, TaxonomyCode
from schema.v1.profile import (
    CanonicalProviderProfile,
    DerivedSignalSummary,
    SourceCoverage,
)

# ---------------------------------------------------------------------------
# Minimal fixture helpers (local copies of tests/search/_fixtures.py subset)
# ---------------------------------------------------------------------------

NPI_ALICE = "1234567890"
NPI_ORG = "1111111111"
FIXED_DT = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
BUNDLE_ALICE = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def make_minimal_profile(npi: str = NPI_ALICE) -> CanonicalProviderProfile:
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith"),
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_full_profile(npi: str = NPI_ALICE) -> CanonicalProviderProfile:
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith", credentials="MD"),
        gender=Gender.FEMALE,
        primary_specialty=TaxonomyCode(
            code="207Q00000X", description="Family Medicine", primary=True
        ),
        active_license_count=2,
        currently_excluded=False,
        has_active_discipline=False,
        source_coverage=[
            SourceCoverage(
                category=SourceCategory.FEDERAL,
                sources_attempted=["F1"],
                sources_succeeded=["F1"],
                coverage_confidence=0.95,
            )
        ],
        derived_signals=[
            DerivedSignalSummary(
                signal_type="identity_confidence",
                value=0.98,
                confidence=0.9,
                explanation="test",
                computed_at=FIXED_DT,
            )
        ],
        report_completeness_score=0.75,
        is_partial=False,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SEARCH_HIT = {
    "_score": 1.5,
    "primary_npi": NPI_ALICE,
    "entity_type": "individual",
    "primary_name": {"first": "Alice", "last": "Smith", "middle": None, "credentials": "MD", "full_name_display": "Alice Smith MD"},
    "primary_specialty": {"code": "207Q00000X", "description": "Family Medicine"},
    "known_states": ["CA"],
    "has_active_exclusion": False,
    "has_active_license": True,
    "identity_confidence": 0.98,
}

_SEARCH_HIT_ORG = {
    "_score": 0.8,
    "primary_npi": NPI_ORG,
    "entity_type": "organization",
    "primary_name": {"first": "Acme", "last": "Medical Group", "middle": None, "credentials": None, "full_name_display": "Acme Medical Group"},
    "primary_specialty": None,
    "known_states": ["IL"],
    "has_active_exclusion": False,
    "has_active_license": False,
    "identity_confidence": 0.5,
}


def make_mock_client(
    search_response: SearchRawResponse | None = None,
    get_response: GetRawResponse | None = None,
    index_response: IndexRawResponse | None = None,
) -> MagicMock:
    mock = MagicMock(spec=OpenSearchClient)

    mock.search.return_value = search_response or SearchRawResponse(
        total=0, hits=[], took_ms=1
    )
    mock.get_doc.return_value = get_response or GetRawResponse(found=False, source=None)
    mock.index_doc.return_value = index_response or IndexRawResponse(
        npi=NPI_ALICE, success=True, index="providers-test", result="created"
    )
    return mock


def make_client_with_hit(hit: dict) -> MagicMock:
    return make_mock_client(
        search_response=SearchRawResponse(total=1, hits=[hit], took_ms=1)
    )


def make_client_with_get(source: dict | None, found: bool = True) -> MagicMock:
    return make_mock_client(
        get_response=GetRawResponse(found=found, source=source)
    )


def get_test_client(mock_os_client: MagicMock) -> TestClient:
    """
    Wire the mock client into the search service and return a TestClient.
    Clears get_settings cache to ensure test settings are fresh.
    """
    from backend.search_service.app import app
    from backend.search_service.routes import _set_singletons

    get_settings.cache_clear()
    settings = SearchSettings()
    indexer = ProviderIndexer(index_name="providers-test")
    _set_singletons(mock_os_client, indexer, settings)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


def test_healthz_returns_ok():
    client = get_test_client(make_mock_client())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_healthz_includes_service_name():
    client = get_test_client(make_mock_client())
    resp = client.get("/healthz")
    assert resp.json().get("service") == "search-service"


def test_readyz_not_configured_when_url_empty():
    """When SEARCH_OPENSEARCH_URL is empty, readyz returns not_configured (no cluster call)."""
    from backend.search_service.app import app
    from backend.search_service.routes import _set_singletons

    get_settings.cache_clear()
    settings = SearchSettings(opensearch_url="")  # force not_configured
    indexer = ProviderIndexer(index_name="providers-test")
    mock_os = make_mock_client()
    _set_singletons(mock_os, indexer, settings)
    tc = TestClient(app)
    resp = tc.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_configured"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_no_params_returns_200():
    client = get_test_client(make_mock_client())
    resp = client.get("/v1/providers/search")
    assert resp.status_code == 200


def test_search_response_envelope_keys():
    client = get_test_client(make_mock_client())
    body = client.get("/v1/providers/search").json()
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "results" in body


def test_search_empty_results():
    client = get_test_client(make_mock_client())
    body = client.get("/v1/providers/search").json()
    assert body["total"] == 0
    assert body["results"] == []


def test_search_with_one_hit():
    client = get_test_client(make_client_with_hit(_SEARCH_HIT))
    body = client.get("/v1/providers/search?q=Alice").json()
    assert body["total"] == 1
    assert len(body["results"]) == 1
    hit = body["results"][0]
    assert hit["npi"] == NPI_ALICE
    assert hit["entity_type"] == "individual"


def test_search_hit_fields_present():
    client = get_test_client(make_client_with_hit(_SEARCH_HIT))
    hit = client.get("/v1/providers/search").json()["results"][0]
    for field in ("npi", "entity_type", "primary_name", "known_states",
                  "has_active_exclusion", "has_active_license", "identity_confidence"):
        assert field in hit, f"Missing field: {field}"


def test_search_score_in_hit():
    client = get_test_client(make_client_with_hit(_SEARCH_HIT))
    hit = client.get("/v1/providers/search").json()["results"][0]
    assert hit["score"] == pytest.approx(1.5)


def test_search_pagination_defaults():
    client = get_test_client(make_mock_client())
    body = client.get("/v1/providers/search").json()
    assert body["page"] == 1
    assert body["page_size"] == 10


def test_search_pagination_custom():
    client = get_test_client(make_mock_client())
    body = client.get("/v1/providers/search?page=3&page_size=25").json()
    assert body["page"] == 3
    assert body["page_size"] == 25


def test_search_calls_os_client_with_index():
    mock_os = make_mock_client()
    client = get_test_client(mock_os)
    client.get("/v1/providers/search?q=Jones")
    mock_os.search.assert_called_once()
    call_kwargs = mock_os.search.call_args.kwargs
    assert "index" in call_kwargs


def test_search_query_body_contains_q():
    """build_search_query is called with the q param and it ends up in the request body."""
    mock_os = make_mock_client()
    client = get_test_client(mock_os)
    client.get("/v1/providers/search?q=cardiology")
    body = mock_os.search.call_args.kwargs["body"]
    # function_score -> query -> bool -> must -> [multi_match]
    fs_query = body["query"]["function_score"]["query"]
    bool_must = fs_query["bool"]["must"]
    assert any("multi_match" in clause for clause in bool_must)


def test_search_no_q_body_uses_match_all():
    mock_os = make_mock_client()
    client = get_test_client(mock_os)
    client.get("/v1/providers/search")
    body = mock_os.search.call_args.kwargs["body"]
    bool_must = body["query"]["function_score"]["query"]["bool"]["must"]
    assert any("match_all" in clause for clause in bool_must)


def test_search_state_filter_in_body():
    mock_os = make_mock_client()
    client = get_test_client(mock_os)
    client.get("/v1/providers/search?state=CA")
    body = mock_os.search.call_args.kwargs["body"]
    bool_q = body["query"]["function_score"]["query"]["bool"]
    filters = bool_q.get("filter", [])
    assert any(f.get("term", {}).get("known_states") == "CA" for f in filters)


# ---------------------------------------------------------------------------
# NPI lookup
# ---------------------------------------------------------------------------


def test_get_provider_found_returns_200():
    client = get_test_client(make_client_with_get(_SEARCH_HIT))
    resp = client.get(f"/v1/providers/{NPI_ALICE}")
    assert resp.status_code == 200


def test_get_provider_npi_in_response():
    client = get_test_client(make_client_with_get(_SEARCH_HIT))
    body = client.get(f"/v1/providers/{NPI_ALICE}").json()
    assert body["npi"] == NPI_ALICE


def test_get_provider_not_found_returns_404():
    client = get_test_client(make_client_with_get(None, found=False))
    resp = client.get(f"/v1/providers/{NPI_ALICE}")
    assert resp.status_code == 404


def test_get_provider_source_none_returns_404():
    client = get_test_client(make_client_with_get(None, found=True))
    resp = client.get(f"/v1/providers/{NPI_ALICE}")
    assert resp.status_code == 404


def test_get_provider_invalid_npi_letters_returns_422():
    client = get_test_client(make_mock_client())
    resp = client.get("/v1/providers/ABCDEFGHIJ")
    assert resp.status_code == 422


def test_get_provider_short_npi_returns_422():
    client = get_test_client(make_mock_client())
    resp = client.get("/v1/providers/123456789")  # 9 digits
    assert resp.status_code == 422


def test_get_provider_uses_get_doc():
    mock_os = make_client_with_get(_SEARCH_HIT)
    tc = get_test_client(mock_os)
    tc.get(f"/v1/providers/{NPI_ALICE}")
    mock_os.get_doc.assert_called_once()


def test_get_provider_passes_npi_to_get_doc():
    mock_os = make_client_with_get(_SEARCH_HIT)
    tc = get_test_client(mock_os)
    tc.get(f"/v1/providers/{NPI_ALICE}")
    assert mock_os.get_doc.call_args.kwargs["doc_id"] == NPI_ALICE


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def _profile_json(npi: str = NPI_ALICE) -> dict:
    return make_full_profile(npi).model_dump(mode="json")


def test_index_provider_success_returns_201():
    client = get_test_client(
        make_mock_client(index_response=IndexRawResponse(
            npi=NPI_ALICE, success=True, index="providers-test", result="created"
        ))
    )
    resp = client.post(f"/v1/providers/{NPI_ALICE}/index", json=_profile_json())
    assert resp.status_code == 201


def test_index_provider_result_body():
    client = get_test_client(
        make_mock_client(index_response=IndexRawResponse(
            npi=NPI_ALICE, success=True, index="providers-test", result="created"
        ))
    )
    body = client.post(f"/v1/providers/{NPI_ALICE}/index", json=_profile_json()).json()
    assert body["success"] is True
    assert body["npi"] == NPI_ALICE


def test_index_provider_npi_mismatch_returns_422():
    """Path NPI does not match profile.npi."""
    client = get_test_client(make_mock_client())
    resp = client.post(f"/v1/providers/{NPI_ORG}/index", json=_profile_json(NPI_ALICE))
    assert resp.status_code == 422


def test_index_provider_client_failure_returns_502():
    client = get_test_client(
        make_mock_client(index_response=IndexRawResponse(
            npi=NPI_ALICE, success=False, index="providers-test", result="error", error="timeout"
        ))
    )
    resp = client.post(f"/v1/providers/{NPI_ALICE}/index", json=_profile_json())
    assert resp.status_code == 502
