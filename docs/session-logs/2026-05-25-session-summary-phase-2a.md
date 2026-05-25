# Session Summary: 2026-05-25 — Phase 2-A (Source Connector Framework, C9)

Per-phase detail log. Opens Phase 2 (Core Identity & MVP).

---

## Summary (readable cold)

Phase 2-A built the **Source Connector Framework (C9)** — the base classes, error handling,
throttling, retry/backoff, and contract testing that every source adapter (C10, Phase 2-B+) is
built on. It lives in `src/connectors/` as a library (adapters run as workers/Temporal activities
later, so there is no deployed service here). It is **framework only**: it fetches no live source.
Real ingestion happens in the C10 adapters and stays governed by the Phase 0 legal gate.

`SourceConnector` (ABC) is the contract an adapter implements via `fetch_raw`; `run()` orchestrates
a full fetch — iterate `fetch_raw`, validate each record against an optional `SchemaContract`,
wrap it in a `RawRecord` (content-addressed SHA-256 via `DataProvenance.hash_raw`, pre-normalization),
time the run, and return a `FetchResult` plus a `SourceHealthRecord` (the existing C24 schema). HTTP
goes through `request()`, which adds client-side throttling (`RateLimiter`), in-house exponential
backoff with full jitter (`retry_with_backoff` — no `tenacity`, honoring `Retry-After`), and
classifies responses into an error taxonomy (429 → rate-limited, 401/403 → auth, 5xx/timeouts →
retryable unavailable, other 4xx → permanent). The `SchemaContract` turns silent schema drift
(architecture risk R6) into an explicit SCHEMA_DRIFT health status, and `testing.py` ships a reusable
`assert_connector_contract` harness so C10 adapters get framework-conformance coverage for free.

The framework is async-first (httpx, per the locked stack); the 21 tests are sync and drive the
coroutines with `asyncio.run`, so no `pytest-asyncio` dependency is added and transports are always
stubbed (no network). Locked as DECISIONS.md Entry 014. 350 pytest + 16 OPA tests pass. Next is
Phase 2-B (Federal Source Adapters: NPPES, OIG LEIE, SAM.gov).

---

## Repo + tracker

- Repo: https://github.com/Alijrob/medpro-review
- Tracker: https://github.com/Alijrob/pagios-ops/blob/main/trackers/medpro-review-phase-tracker.md

---

## Files changed / added (by area)

- **Connector framework (new):** `src/connectors/{__init__,base,config,models,errors,retry,throttle,contract,testing}.py`, `README.md`.
- **Decisions:** `DECISIONS.md` Entry 014.
- **Wiring:** `pyproject.toml` (packages += connectors), `Makefile` (`connectors-test`), `.github/workflows/connectors-validate.yml` (new).
- **Tests:** `tests/connectors/test_framework.py` (21), `tests/connectors/__init__.py`.
- **Docs:** onboarding (Phase 2-A complete; 2-B next).

---

## Phase status

- Phase 2-A (Source Connector Framework, C9): COMPLETE.
- Phase 2-B (Federal Source Adapters, C10): UP NEXT.
- Phases 0 through 1-I: complete (Phase 1 foundations done).

---

## Next likely step

Phase 2-B — Federal Source Adapters (C10): NPPES/NPI (F1), OIG LEIE (F2), SAM.gov Exclusions (F3),
each a `SourceConnector` subclass with a `SchemaContract` and an `assert_connector_contract` test.
These ingest real data, so each is governed by the Phase 0 legal gate (all three are T1/L0
open-data, the lowest-risk tier). Build NPPES first — it is the identity anchor for all downstream
identity resolution.

---

## Verified checks

- `PYTHONPATH=src pytest tests/ -m "not integration"` => 350 passed, 7 deselected (44 schema + 20 data + 39 observability + 179 gitops + 47 backend + 21 connectors).
- `opa test src/policy` => 16/16 PASS (unchanged).
- `import connectors` exposes the 16-symbol public API.
- Retry tests confirm: transient retried then success, permanent not retried, exhaustion re-raises, `Retry-After` floors the delay. HTTP classification tests confirm 500→DOWN(retried), 429→RATE_LIMITED, 401→AUTH_FAILED(not retried), transport error→recovered.

---

## Blocked / unverified

- The default `httpx.AsyncClient` transport path is present but untested (tests always inject a stub) — exercised when the first real adapter lands in 2-B.
- The per-instance `RateLimiter` is a per-replica floor; a Redis-backed global limiter is layered on when adapters run multi-replica.
- No live source is contacted (framework only); the C10 adapters remain behind the Phase 0 legal gate.

---

## Tests run

```
PYTHONPATH=src pytest tests/ -m "not integration"
=> 350 passed, 7 deselected
   44 schema | 20 data | 39 observability | 179 gitops | 47 backend | 21 connectors
opa test src/policy                               => PASS 16/16
```
