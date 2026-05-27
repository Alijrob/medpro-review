"""
test_google_places.py -- Google Places review platform adapter tests (Phase 3-E, R1).

Exercises GooglePlacesConnector against stub transports (no live network).
Tests cover: config identity, contract harness (with dummy api_key), cursor pagination
via next_page_token, absent-token termination, api_key as query param, query string
forwarded, camelCase field normalization, numeric-to-str coercion for rating and
user_ratings_total, None reviews coerced to [], reviews setdefault when absent from
response, schema drift, failure modes, and AuthenticationError when api_key is absent.

Run:
    PYTHONPATH=src pytest tests/connectors/test_google_places.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.review_platforms import GooglePlacesConnector, google_places_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

_DUMMY_KEY = "test-gp-api-key"


# --- helpers ------------------------------------------------------------------

def _gp_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "place_id": "ChIJabcdef1234567890",
        "name": "Dr. Sarah Chen, MD",
        "rating": "4.7",
        "user_ratings_total": "312",
        "formatted_address": "456 Oak Ave, San Francisco, CA 94102",
        "reviews": [],
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, Any]], next_token: str | None = None) -> StubResponse:
    body: dict[str, Any] = {"status": "OK", "results": rows}
    if next_token:
        body["next_page_token"] = next_token
    return StubResponse(json_body=body)


def _recording_transport(*responses: StubResponse):
    calls: list[dict[str, Any]] = []
    seq = list(responses)

    async def _t(method: str, url: str, **kwargs: Any) -> StubResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return _t, calls


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_google_places(self):
        cfg = google_places_config()
        assert cfg.source_id == "google_places"
        assert cfg.source_name == "Google Places Provider Reviews"
        assert cfg.source_category is SourceCategory.REVIEW_PLATFORM
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_googleapis(self):
        cfg = google_places_config()
        assert "googleapis.com" in cfg.base_url

    def test_overrides_apply(self):
        cfg = google_places_config(rate_limit_per_sec=2.0)
        assert cfg.rate_limit_per_sec == 2.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_gp_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_gp_row(), _gp_row(place_id="ChIJxyz")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_gp_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "google_places" for r in result.records)


# ---------------------------------------------------------------------------
class TestPagination:
    def test_absent_next_page_token_terminates(self):
        """Single page with no next_page_token ends immediately."""
        transport, calls = _recording_transport(_page([_gp_row()]))
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 1
        assert len(calls) == 1

    def test_next_page_token_triggers_second_request(self):
        """next_page_token in first response triggers a second fetch."""
        transport, calls = _recording_transport(
            _page([_gp_row(place_id="p1"), _gp_row(place_id="p2")], next_token="tok_abc"),
            _page([_gp_row(place_id="p3")]),  # no token = last page
        )
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2

    def test_pagetoken_sent_on_second_request(self):
        """The next_page_token from page 1 is forwarded as pagetoken param."""
        transport, calls = _recording_transport(
            _page([_gp_row()], next_token="tok_xyz"),
            _page([_gp_row(place_id="p2")]),
        )
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[1]["params"].get("pagetoken") == "tok_xyz"

    def test_empty_results_terminates(self):
        transport, calls = _recording_transport(_page([]))
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 0
        assert len(calls) == 1

    def test_three_pages_collected(self):
        transport, calls = _recording_transport(
            _page([_gp_row(place_id="p1"), _gp_row(place_id="p2")], next_token="t1"),
            _page([_gp_row(place_id="p3"), _gp_row(place_id="p4")], next_token="t2"),
            _page([_gp_row(place_id="p5")]),
        )
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 5
        assert len(calls) == 3


# ---------------------------------------------------------------------------
class TestAuthParam:
    def test_api_key_sent_as_query_param(self):
        transport, calls = _recording_transport(_page([_gp_row()]))
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key="my-secret-key",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["key"] == "my-secret-key"

    def test_query_string_forwarded(self):
        transport, calls = _recording_transport(_page([_gp_row()]))
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            query="Dr. Jones internist Chicago",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["query"] == "Dr. Jones internist Chicago"

    def test_no_api_key_returns_failed(self):
        """Without api_key, run() returns FAILED with an authentication error."""
        conn = GooglePlacesConnector(google_places_config())
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert any("api_key" in e for e in result.errors)


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_place_id_normalized(self):
        row = {
            "placeId": "ChIJabc",
            "name": "Dr. Wu",
            "rating": "4.1",
            "user_ratings_total": "55",
            "formatted_address": "1 Main St",
        }
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["place_id"] == "ChIJabc"

    def test_camel_case_user_ratings_total_normalized(self):
        row = {
            "place_id": "ChIJabc",
            "name": "Dr. Wu",
            "rating": "4.1",
            "userRatingsTotal": 99,
            "formatted_address": "1 Main St",
        }
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["user_ratings_total"] == "99"

    def test_numeric_rating_coerced_to_str(self):
        row = _gp_row(rating=4.7)
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["rating"], str)
        assert result.records[0].raw["rating"] == "4.7"

    def test_numeric_user_ratings_total_coerced_to_str(self):
        row = _gp_row(user_ratings_total=312)
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["user_ratings_total"], str)

    def test_none_reviews_coerced_to_list(self):
        row = _gp_row(reviews=None)
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["reviews"] == []

    def test_reviews_defaulted_when_absent_from_response(self):
        """Text Search responses omit the reviews key -- setdefault ensures it's present."""
        row = {
            "place_id": "ChIJabc",
            "name": "Dr. Kim",
            "rating": "4.3",
            "user_ratings_total": "44",
            "formatted_address": "99 Pine St",
            # no "reviews" key at all
        }
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["reviews"] == []


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        good = _gp_row()
        bad = _gp_row()
        del bad["rating"]
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([good, bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_dict_response_fails_gracefully(self):
        stub = StubResponse(json_body=["bare", "list"])
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_list_results_key_fails_gracefully(self):
        stub = StubResponse(json_body={"status": "OK", "results": "not-a-list"})
        conn = GooglePlacesConnector(
            google_places_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
