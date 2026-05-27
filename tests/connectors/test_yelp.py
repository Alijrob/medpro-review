"""
test_yelp.py -- Yelp Fusion review platform adapter tests (Phase 3-E, R2).

Exercises YelpConnector against stub transports (no live network).
Tests cover: config identity, contract harness (with dummy api_key), offset/limit
pagination with short-page sentinel, Yelp 1000-result hard cap enforcement,
Authorization Bearer header, term/location forwarded as params, numeric-to-str
coercion for rating/review_count, None location coerced to {}, None categories
coerced to [], schema drift, failure modes, and AuthenticationError when api_key
is absent.

Run:
    PYTHONPATH=src pytest tests/connectors/test_yelp.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.review_platforms import YelpConnector, yelp_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

_DUMMY_KEY = "test-yelp-bearer-token"


# --- helpers ------------------------------------------------------------------

def _yp_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "dr-michael-torres-chicago",
        "name": "Dr. Michael Torres, MD",
        "rating": "4.5",
        "review_count": "89",
        "location": {
            "address1": "789 Elm St",
            "city": "Chicago",
            "state": "IL",
            "zip_code": "60601",
        },
        "categories": [{"alias": "internalmedicine", "title": "Internal Medicine"}],
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, Any]], total: int | None = None) -> StubResponse:
    body: dict[str, Any] = {"businesses": rows}
    if total is not None:
        body["total"] = total
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
    def test_identity_is_yelp(self):
        cfg = yelp_config()
        assert cfg.source_id == "yelp"
        assert cfg.source_name == "Yelp Fusion Provider Reviews"
        assert cfg.source_category is SourceCategory.REVIEW_PLATFORM
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_yelp(self):
        cfg = yelp_config()
        assert "yelp.com" in cfg.base_url

    def test_overrides_apply(self):
        cfg = yelp_config(rate_limit_per_sec=2.0)
        assert cfg.rate_limit_per_sec == 2.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_yp_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_yp_row(), _yp_row(id="dr-kim-chicago")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_yp_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "yelp" for r in result.records)


# ---------------------------------------------------------------------------
class TestPagination:
    def test_short_page_terminates(self):
        """Last page shorter than page_size ends pagination."""
        transport, calls = _recording_transport(
            _page([_yp_row(id="b1"), _yp_row(id="b2")]),
            _page([_yp_row(id="b3")]),  # short page
        )
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2

    def test_full_pages_continue_until_short(self):
        transport, calls = _recording_transport(
            _page([_yp_row(id="b1"), _yp_row(id="b2")]),
            _page([_yp_row(id="b3"), _yp_row(id="b4")]),
            _page([_yp_row(id="b5")]),
        )
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 5
        assert len(calls) == 3

    def test_empty_page_terminates_immediately(self):
        transport, calls = _recording_transport(_page([]))
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 0
        assert len(calls) == 1

    def test_offset_advances_by_page_size(self):
        transport, calls = _recording_transport(
            _page([_yp_row(id="b1"), _yp_row(id="b2")]),
            _page([_yp_row(id="b3")]),
        )
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["offset"] == 0
        assert calls[1]["params"]["offset"] == 2

    def test_yelp_1000_cap_prevents_further_requests(self):
        """When offset reaches 1000, no further requests are made."""
        # page_size=500: first call at offset 0 returns 500, second would be at 500,
        # third at 1000 -- which hits the cap and must NOT fire.
        transport, calls = _recording_transport(
            _page([_yp_row(id=f"b{i}") for i in range(500)]),
            _page([_yp_row(id=f"b{i}") for i in range(500, 1000)]),
            # third call should never be made
            _page([_yp_row(id="should_not_appear")]),
        )
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=500,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 1000
        assert len(calls) == 2  # offset 0, offset 500 -- NOT offset 1000


# ---------------------------------------------------------------------------
class TestAuthHeader:
    def test_bearer_header_sent(self):
        transport, calls = _recording_transport(_page([_yp_row()]))
        conn = YelpConnector(
            yelp_config(),
            api_key="my-bearer-secret",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["headers"]["Authorization"] == "Bearer my-bearer-secret"

    def test_term_and_location_forwarded(self):
        transport, calls = _recording_transport(_page([_yp_row()]))
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            term="internist",
            location="Chicago, IL",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["term"] == "internist"
        assert calls[0]["params"]["location"] == "Chicago, IL"

    def test_no_api_key_returns_failed(self):
        """Without api_key, run() returns FAILED with an authentication error."""
        conn = YelpConnector(yelp_config())
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert any("api_key" in e for e in result.errors)


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_numeric_rating_coerced_to_str(self):
        row = _yp_row(rating=4.5)
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["rating"], str)
        assert result.records[0].raw["rating"] == "4.5"

    def test_numeric_review_count_coerced_to_str(self):
        row = _yp_row(review_count=89)
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["review_count"], str)

    def test_none_location_coerced_to_dict(self):
        row = _yp_row(location=None)
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["location"] == {}

    def test_none_categories_coerced_to_list(self):
        row = _yp_row(categories=None)
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["categories"] == []

    def test_location_and_categories_defaulted_when_absent(self):
        """Ensure setdefault fills missing location/categories even when key absent."""
        row = {
            "id": "biz-abc",
            "name": "Dr. Patel",
            "rating": "4.0",
            "review_count": "12",
            # no location or categories keys
        }
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert raw["location"] == {}
        assert raw["categories"] == []


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        good = _yp_row()
        bad = _yp_row()
        del bad["rating"]
        conn = YelpConnector(
            yelp_config(),
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
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_dict_response_fails_gracefully(self):
        stub = StubResponse(json_body=["bare", "list"])
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_list_businesses_key_fails_gracefully(self):
        stub = StubResponse(json_body={"total": 1, "businesses": "not-a-list"})
        conn = YelpConnector(
            yelp_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
