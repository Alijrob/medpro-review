"""
base.py — SourceConnector abstract base (component C9).

The contract every source adapter (C10, Phase 2-B+) implements. An adapter
subclasses SourceConnector and implements `fetch_raw` (the source-specific
extraction), typically using `self.request(...)` for HTTP so it inherits
throttling, retry/backoff, and error classification for free. `run()` orchestrates
a full fetch: it iterates `fetch_raw`, validates each record against the optional
schema contract, wraps records with provenance hashes, times the run, and builds a
FetchResult + SourceHealthRecord (consumed by C24, the Source Health Monitor).

Output is RawRecords (pre-normalization). Turning them into typed NormalizedRecords
is C11 (Normalization Layer, Phase 2-D).

NOTE: this is the framework only. No live source is fetched here — the Phase 0 legal
gate governs real ingestion, which happens in the C10 adapters.
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from schema.v1.common import SourceCategory, utc_now
from schema.v1.source_health import SourceHealthRecord, SourceStatus

from .config import ConnectorConfig
from .contract import SchemaContract
from .errors import (
    AuthenticationError,
    ConnectorError,
    PermanentError,
    RateLimitedError,
    SourceUnavailableError,
)
from .models import FetchResult, FetchStatus, IntegrationMethod, RawRecord
from .retry import retry_with_backoff
from .throttle import RateLimiter

# A transport is any async callable (method, url, **kwargs) -> response-like object
# exposing `.status_code`, `.headers`, and (for adapters) `.json()` / `.text`.
Transport = Callable[..., Awaitable[Any]]


class SourceConnector(ABC):
    """Base class for all source connectors."""

    # Adapters may set a SchemaContract to enable runtime schema-drift detection.
    contract: SchemaContract | None = None

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        transport: Transport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self._limiter = RateLimiter(config.rate_limit_per_sec, clock=clock, sleep=sleep)
        self._retries = 0
        self._client: Any | None = None

    # --- identity ----------------------------------------------------------
    @property
    def source_id(self) -> str:
        return self.config.source_id

    @property
    def source_category(self) -> SourceCategory:
        return self.config.source_category

    @property
    def integration_method(self) -> IntegrationMethod:
        return self.config.integration_method

    # --- the source-specific bit (adapters implement) ---------------------
    @abstractmethod
    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Yield raw record dicts from the source. Use `self.request` for HTTP."""
        raise NotImplementedError
        yield {}  # pragma: no cover  (marks this an async generator for typing)

    # --- HTTP with throttle + retry + classification ----------------------
    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Throttled, retried HTTP call. Classifies the response into ConnectorErrors."""
        await self._limiter.acquire()

        async def _do() -> Any:
            try:
                resp = await self._call_transport(method, url, **kwargs)
            except ConnectorError:
                raise
            except Exception as exc:  # transport-level (timeout, connection reset)
                raise SourceUnavailableError(f"transport error: {exc}") from exc
            self._raise_for_status(resp)
            return resp

        return await retry_with_backoff(
            _do,
            max_retries=self.config.max_retries,
            base_delay=self.config.backoff_base_seconds,
            max_delay=self.config.backoff_max_seconds,
            sleep=self._sleep,
            on_retry=lambda attempt, exc: self._note_retry(),
        )

    def _note_retry(self) -> None:
        self._retries += 1

    @staticmethod
    def _retry_after_seconds(headers: Any) -> float | None:
        value = headers.get("Retry-After") if hasattr(headers, "get") else None
        if value is not None and str(value).isdigit():
            return float(value)
        return None

    def _raise_for_status(self, resp: Any) -> None:
        sc = int(resp.status_code)
        if sc < 400:
            return
        if sc == 429:
            raise RateLimitedError(
                f"{self.source_id}: HTTP 429 (rate limited)",
                retry_after=self._retry_after_seconds(resp.headers),
            )
        if sc in (401, 403):
            raise AuthenticationError(f"{self.source_id}: HTTP {sc} (auth)")
        if sc >= 500:
            raise SourceUnavailableError(f"{self.source_id}: HTTP {sc}")
        raise PermanentError(f"{self.source_id}: HTTP {sc}")

    async def _call_transport(self, method: str, url: str, **kwargs: Any) -> Any:
        if self._transport is not None:
            return await self._transport(method, url, **kwargs)
        client = await self._get_client()
        return await client.request(method, url, timeout=self.config.timeout_seconds, **kwargs)

    async def _get_client(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # --- orchestration -----------------------------------------------------
    async def run(self) -> FetchResult:
        """Fetch everything, validating contract + wrapping with provenance, then report."""
        start = self._clock()
        records: list[RawRecord] = []
        errors: list[str] = []
        source_status: SourceStatus | None = None
        self._retries = 0

        try:
            async for raw in self.fetch_raw():
                if self.contract is not None:
                    self.contract.validate(raw)
                records.append(
                    RawRecord.from_raw(
                        self.source_id, raw, schema_version=self.config.schema_version
                    )
                )
        except ConnectorError as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            source_status = exc.to_status()

        duration_ms = (self._clock() - start) * 1000.0

        if errors:
            status = FetchStatus.PARTIAL if records else FetchStatus.FAILED
        else:
            status = FetchStatus.SUCCESS
            expected_min = self.config.expected_min_records
            if expected_min is not None and len(records) < expected_min:
                status = FetchStatus.PARTIAL
                errors.append(
                    f"record count {len(records)} below expected_min_records {expected_min}"
                )

        health = self._build_health(
            status=status,
            source_status=source_status,
            duration_ms=duration_ms,
            record_count=len(records),
            errors=errors,
        )
        return FetchResult(
            source_id=self.source_id,
            status=status,
            records=records,
            record_count=len(records),
            error_count=len(errors),
            errors=errors,
            duration_ms=duration_ms,
            retries=self._retries,
            health=health,
        )

    def _build_health(
        self,
        *,
        status: FetchStatus,
        source_status: SourceStatus | None,
        duration_ms: float,
        record_count: int,
        errors: list[str],
    ) -> SourceHealthRecord:
        now = utc_now()
        failed = status is FetchStatus.FAILED
        if status is FetchStatus.SUCCESS:
            health_status = SourceStatus.HEALTHY
        elif status is FetchStatus.PARTIAL:
            health_status = source_status or SourceStatus.DEGRADED
        else:
            health_status = source_status or SourceStatus.DOWN

        is_bulk = self.integration_method is IntegrationMethod.BULK_DOWNLOAD
        drift = health_status is SourceStatus.SCHEMA_DRIFT
        joined = "; ".join(errors)
        return SourceHealthRecord(
            source_id=self.source_id,
            source_name=self.config.source_name,
            source_category=self.config.source_category,
            status=health_status,
            last_checked_at=now,
            last_successful_at=None if failed else now,
            last_failed_at=now if failed else None,
            consecutive_failures=1 if failed else 0,
            consecutive_successes=0 if failed else 1,
            avg_latency_ms=duration_ms,
            expected_schema_version=self.config.schema_version,
            schema_drift_detected=drift,
            schema_drift_details=joined if drift else None,
            schema_drift_first_seen_at=now if drift else None,
            last_bulk_download_at=now if (is_bulk and not failed) else None,
            bulk_download_record_count=record_count if is_bulk else None,
            bulk_download_expected_min=self.config.expected_min_records,
            notes=(joined[:500] or None),
        )
