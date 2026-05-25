"""
test_framework.py — Phase 2-A Source Connector Framework (C9) unit tests.

The framework is async-first; these are plain sync tests that drive the coroutines
with asyncio.run (no pytest-asyncio dependency). They exercise real behavior: hashing,
the schema-drift contract, retry/backoff classification, throttling, the run()
orchestration + health snapshot, and the reusable contract-test harness.

Run:
    PYTHONPATH=src pytest tests/connectors/ -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import (
    ConnectorConfig,
    FetchStatus,
    IntegrationMethod,
    RawRecord,
    SchemaContract,
    SourceConnector,
    retry_with_backoff,
)
from connectors.errors import (
    AuthenticationError,
    PermanentError,
    RateLimitedError,
    SourceUnavailableError,
    TransientError,
)
from connectors.testing import (
    StubResponse,
    assert_connector_contract,
    recording_sleep,
    stub_transport,
)
from connectors.throttle import RateLimiter
from schema.v1.common import DataProvenance, SourceCategory
from schema.v1.source_health import SourceStatus


def cfg(method: IntegrationMethod = IntegrationMethod.REST_API, **kw: Any) -> ConnectorConfig:
    base = dict(
        source_id="F1",
        source_name="NPPES NPI Registry",
        source_category=SourceCategory.FEDERAL,
        integration_method=method,
        max_retries=2,
        backoff_base_seconds=0.1,
        backoff_max_seconds=1.0,
    )
    base.update(kw)
    return ConnectorConfig(**base)


# --- adapters used only by these tests -------------------------------------
class ListConnector(SourceConnector):
    """Yields a fixed list of raw dicts (no HTTP)."""

    def __init__(self, config: ConnectorConfig, items: list[dict], **kw: Any) -> None:
        super().__init__(config, **kw)
        self._items = items

    async def fetch_raw(self):
        for item in self._items:
            yield item


class HttpConnector(SourceConnector):
    """Fetches a JSON array over HTTP and yields each element."""

    async def fetch_raw(self):
        resp = await self.request("GET", "/data")
        for item in resp.json():
            yield item


# ---------------------------------------------------------------------------
class TestRawRecord:
    def test_hash_is_deterministic_and_matches_provenance(self):
        raw = {"npi": "1234567890", "name": "Doe"}
        r1 = RawRecord.from_raw("F1", raw)
        r2 = RawRecord.from_raw("F1", dict(reversed(list(raw.items()))))  # key order irrelevant
        assert r1.raw_record_hash == r2.raw_record_hash
        assert r1.raw_record_hash == DataProvenance.hash_raw(raw)

    def test_hash_is_content_addressed_not_source_scoped(self):
        raw = {"a": 1}
        assert RawRecord.from_raw("F1", raw).raw_record_hash == RawRecord.from_raw("F2", raw).raw_record_hash


# ---------------------------------------------------------------------------
class TestSchemaContract:
    contract = SchemaContract(required_fields=frozenset({"npi", "name"}), field_types={"npi": str})

    def test_conformant_passes(self):
        self.contract.validate({"npi": "1", "name": "Doe", "extra": 1})  # no raise

    def test_missing_field_raises(self):
        with pytest.raises(Exception) as e:
            self.contract.validate({"npi": "1"})
        assert "missing required fields" in str(e.value)

    def test_wrong_type_raises(self):
        with pytest.raises(Exception) as e:
            self.contract.validate({"npi": 1, "name": "Doe"})
        assert "expected str" in str(e.value)


# ---------------------------------------------------------------------------
class TestRetry:
    def test_retries_transient_then_succeeds(self):
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise TransientError("boom")
            return "ok"

        sleep, delays = recording_sleep()
        out = asyncio.run(
            retry_with_backoff(flaky, max_retries=5, base_delay=0.1, max_delay=1.0,
                               sleep=sleep, rng=lambda: 1.0)
        )
        assert out == "ok"
        assert calls["n"] == 3
        assert len(delays) == 2  # two retries before the success

    def test_permanent_not_retried(self):
        calls = {"n": 0}

        async def boom():
            calls["n"] += 1
            raise PermanentError("nope")

        sleep, delays = recording_sleep()
        with pytest.raises(PermanentError):
            asyncio.run(retry_with_backoff(boom, max_retries=5, base_delay=0.1, max_delay=1.0, sleep=sleep))
        assert calls["n"] == 1
        assert delays == []

    def test_exhaustion_reraises(self):
        async def always():
            raise TransientError("again")

        sleep, _ = recording_sleep()
        with pytest.raises(TransientError):
            asyncio.run(retry_with_backoff(always, max_retries=2, base_delay=0.1, max_delay=1.0, sleep=sleep))

    def test_rate_limit_retry_after_is_a_floor(self):
        async def limited():
            raise RateLimitedError("429", retry_after=5.0)

        sleep, delays = recording_sleep()
        with pytest.raises(RateLimitedError):
            asyncio.run(
                retry_with_backoff(limited, max_retries=1, base_delay=0.1, max_delay=1.0,
                                   sleep=sleep, rng=lambda: 0.0)
            )
        assert delays and delays[0] >= 5.0  # retry_after floors the jittered delay


# ---------------------------------------------------------------------------
class TestRateLimiter:
    def test_spaces_calls_by_min_interval(self):
        sleep, delays = recording_sleep()
        rl = RateLimiter(10.0, clock=lambda: 0.0, sleep=sleep)  # 10/s => 0.1s interval

        async def two():
            await rl.acquire()
            await rl.acquire()

        asyncio.run(two())
        assert delays == [pytest.approx(0.1)]

    def test_unlimited_never_sleeps(self):
        sleep, delays = recording_sleep()
        rl = RateLimiter(0.0, clock=lambda: 0.0, sleep=sleep)

        async def two():
            await rl.acquire()
            await rl.acquire()

        asyncio.run(two())
        assert delays == []


# ---------------------------------------------------------------------------
class TestRunOrchestration:
    def test_success_yields_records_and_healthy(self):
        conn = ListConnector(cfg(IntegrationMethod.BULK_DOWNLOAD), [{"npi": "1"}, {"npi": "2"}])
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY
        assert result.health.bulk_download_record_count == 2  # bulk method populates this

    def test_partial_when_below_expected_min(self):
        conn = ListConnector(cfg(expected_min_records=5), [{"npi": "1"}])
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert any("below expected_min_records" in e for e in result.errors)

    def test_schema_drift_flagged(self):
        conn = ListConnector(cfg(), [{"npi": "1"}, {"oops": 1}])
        conn.contract = SchemaContract(required_fields=frozenset({"npi"}))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL          # one good record before the drift
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_http_success(self):
        conn = HttpConnector(
            cfg(), transport=stub_transport(StubResponse(json_body=[{"npi": "1"}, {"npi": "2"}]))
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2

    def test_http_500_retried_then_failed_down(self):
        sleep, delays = recording_sleep()
        conn = HttpConnector(cfg(max_retries=2), transport=stub_transport(StubResponse(status_code=500)), sleep=sleep)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN
        assert result.retries == 2          # retried max_retries times before giving up
        assert len(delays) == 2

    def test_http_429_sets_rate_limited(self):
        sleep, _ = recording_sleep()
        conn = HttpConnector(
            cfg(max_retries=1),
            transport=stub_transport(StubResponse(status_code=429, headers={"Retry-After": "1"})),
            sleep=sleep,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.RATE_LIMITED

    def test_http_401_not_retried_auth_failed(self):
        sleep, delays = recording_sleep()
        conn = HttpConnector(cfg(max_retries=3), transport=stub_transport(StubResponse(status_code=401)), sleep=sleep)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.AUTHENTICATION_FAILED
        assert result.retries == 0          # auth errors are not retryable
        assert delays == []

    def test_transport_error_retried_then_recovers(self):
        sleep, _ = recording_sleep()
        conn = HttpConnector(
            cfg(max_retries=3),
            transport=stub_transport(ConnectionResetError("reset"), StubResponse(json_body=[{"npi": "1"}])),
            sleep=sleep,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1
        assert result.retries == 1


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_harness_passes_for_conformant_connector(self):
        conn = HttpConnector(cfg(), transport=stub_transport(StubResponse(json_body=[{"npi": "1"}])))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_harness_fails_for_broken_connector(self):
        conn = HttpConnector(cfg(max_retries=0), transport=stub_transport(StubResponse(status_code=500)))
        with pytest.raises(AssertionError):
            asyncio.run(assert_connector_contract(conn))
