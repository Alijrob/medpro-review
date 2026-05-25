"""
store.py — HealthStore: in-memory health state + history aggregation (C24).

The HealthStore is the stateful counterpart to the stateless SourceHealthMonitor.
It accumulates SourceHealthRecord snapshots from adapter runs and tracks:

  - Current state per source (last-run snapshot, updated on each ingest)
  - Accumulated consecutive_failures / consecutive_successes across runs
    (base.py always emits 0 or 1; the store builds the true running count)
  - Recent history (ring buffer, last `history_limit` records per source)
  - Alert suppressions (source_id -> suppress_until datetime)

In deployed environments this is backed by Aurora:
  - current state  -> upsert into source_health_records (migration 0001)
  - history        -> INSERT into source_health_history (migration 0004)

The ring buffer is the in-memory shell; production persists both to Aurora.
"""
from __future__ import annotations

import dataclasses
from collections import deque
from datetime import datetime

from connectors.models import IntegrationMethod
from schema.v1.common import SourceCategory, utc_now
from schema.v1.source_health import SourceHealthRecord, SourceStatus


# ---------------------------------------------------------------------------
# P1 source registry
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class _SourceMeta:
    source_id: str
    source_name: str
    category: SourceCategory
    integration_method: IntegrationMethod


# The 8 P1 sources that have SourceConnector implementations (Phase 2-B).
# I4 (NPPES Specialty Crosswalk) is a derived helper, not a connector;
# it does not emit SourceHealthRecords and is excluded from the monitor.
_P1_SOURCES: list[_SourceMeta] = [
    _SourceMeta("F1", "NPPES NPI Registry",          SourceCategory.FEDERAL,   IntegrationMethod.REST_API),
    _SourceMeta("F2", "OIG LEIE Exclusion Database", SourceCategory.FEDERAL,   IntegrationMethod.BULK_DOWNLOAD),
    _SourceMeta("F3", "SAM.gov Exclusions",          SourceCategory.FEDERAL,   IntegrationMethod.REST_API),
    _SourceMeta("F4", "CMS Care Compare",            SourceCategory.FEDERAL,   IntegrationMethod.REST_API),
    _SourceMeta("I1", "CMS Medicare Enrollment",     SourceCategory.FEDERAL,   IntegrationMethod.REST_API),
    _SourceMeta("I2", "CMS Medicaid Enrollment",     SourceCategory.FEDERAL,   IntegrationMethod.REST_API),
    _SourceMeta("A1", "PubMed / NCBI Entrez",        SourceCategory.ACADEMIC,  IntegrationMethod.REST_API),
    _SourceMeta("A2", "ClinicalTrials.gov",          SourceCategory.ACADEMIC,  IntegrationMethod.REST_API),
]

_P1_BY_ID: dict[str, _SourceMeta] = {s.source_id: s for s in _P1_SOURCES}


def get_p1_sources() -> list[_SourceMeta]:
    """Return the ordered list of P1 source metadata entries."""
    return list(_P1_SOURCES)


def get_source_meta(source_id: str) -> _SourceMeta | None:
    """Look up a P1 source by ID. Returns None for unknown / non-P1 sources."""
    return _P1_BY_ID.get(source_id)


# ---------------------------------------------------------------------------
# HealthStore
# ---------------------------------------------------------------------------

class HealthStore:
    """
    In-memory health state store for the Source Health Monitor (C24).

    Thread-safety: this class is not thread-safe. In production it would be
    replaced by async Aurora reads/writes; the in-memory shell is single-threaded
    (FastAPI async event loop).
    """

    def __init__(self, history_limit: int = 100) -> None:
        self._history_limit = history_limit
        self._current: dict[str, SourceHealthRecord] = {}
        self._history: dict[str, deque[SourceHealthRecord]] = {}
        self._failures: dict[str, int] = {}   # accumulated consecutive failures
        self._successes: dict[str, int] = {}  # accumulated consecutive successes
        self._suppressed_until: dict[str, datetime] = {}
        self._seed_p1_sources()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def ingest(self, record: SourceHealthRecord) -> None:
        """
        Accept a SourceHealthRecord from an adapter run.

        - Updates the current state for that source.
        - Appends to the history ring buffer.
        - Accumulates consecutive_failures / consecutive_successes.

        Note: base.py emits consecutive_failures of 0 (success) or 1 (failure)
        for the single run. This method builds the running total across runs.
        """
        sid = record.source_id

        # Initialize history deque if first ingest for this source.
        if sid not in self._history:
            self._history[sid] = deque(maxlen=self._history_limit)
        if sid not in self._failures:
            self._failures[sid] = 0
        if sid not in self._successes:
            self._successes[sid] = 0

        # Update running consecutive counters.
        run_failed = record.consecutive_failures > 0  # base.py emits 1 if failed
        if run_failed:
            self._failures[sid] += 1
            self._successes[sid] = 0
        else:
            self._successes[sid] += 1
            self._failures[sid] = 0

        # Store current state and history.
        self._current[sid] = record
        self._history[sid].appendleft(record)

    def suppress(self, source_id: str, until: datetime) -> None:
        """Suppress health alerts for `source_id` until `until`."""
        self._suppressed_until[source_id] = until

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def current(self, source_id: str) -> SourceHealthRecord | None:
        """Return the most recent SourceHealthRecord for `source_id`, or None."""
        return self._current.get(source_id)

    def all_current(self) -> list[SourceHealthRecord]:
        """Return current SourceHealthRecords for all sources (including unseeded unknowns)."""
        return list(self._current.values())

    def history(self, source_id: str, limit: int = 20) -> list[SourceHealthRecord]:
        """Return recent history for `source_id`, newest-first (up to `limit` entries)."""
        dq = self._history.get(source_id)
        if dq is None:
            return []
        return list(dq)[:limit]

    def accumulated_failures(self, source_id: str) -> int:
        """Accumulated consecutive failure count for `source_id`."""
        return self._failures.get(source_id, 0)

    def accumulated_successes(self, source_id: str) -> int:
        """Accumulated consecutive success count for `source_id`."""
        return self._successes.get(source_id, 0)

    def is_suppressed(self, source_id: str, now: datetime | None = None) -> bool:
        """Return True if alerts for `source_id` are currently suppressed."""
        until = self._suppressed_until.get(source_id)
        if until is None:
            return False
        return (now or utc_now()) < until

    def integration_method(self, source_id: str) -> IntegrationMethod:
        """
        Return the integration method for `source_id`.
        Defaults to REST_API for unknown sources (safest: shorter stale threshold).
        """
        meta = _P1_BY_ID.get(source_id)
        return meta.integration_method if meta else IntegrationMethod.REST_API

    def source_ids(self) -> list[str]:
        """Return all source IDs currently tracked (seeded + ingested)."""
        return list(self._current.keys())

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------

    def _seed_p1_sources(self) -> None:
        """Pre-seed all 9 P1 source IDs as UNKNOWN so the fleet summary is
        populated from startup, mirroring the Aurora 0003 + 0004 seed rows."""
        for meta in _P1_SOURCES:
            record = SourceHealthRecord(
                source_id=meta.source_id,
                source_name=meta.source_name,
                source_category=meta.category,
                status=SourceStatus.UNKNOWN,
            )
            self._current[meta.source_id] = record
            self._history[meta.source_id] = deque(maxlen=self._history_limit)
            self._failures[meta.source_id] = 0
            self._successes[meta.source_id] = 0
