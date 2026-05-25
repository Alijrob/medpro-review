# Source Health Monitor (C24) — Phase 2-C

FastAPI service that aggregates `SourceHealthRecord` snapshots from adapter
runs, evaluates alert thresholds, and exposes a fleet health dashboard for
all 8 P1 federal data source connectors.

**DECISIONS.md Entry 024** — design rationale and deferred items.

---

## Architecture

```
Adapter (C10) --[FetchResult.health]--> POST /v1/sources/{id}/ingest
                                              |
                                        HealthStore (in-memory)
                                              |
                                   SourceHealthMonitor.evaluate()
                                              |
                               GET /v1/sources  /v1/alerts  /v1/sources/{id}
```

### Two key classes

| Class | File | Role |
|-------|------|------|
| `HealthStore` | `store.py` | Stateful: ingests records, accumulates consecutive counters, ring-buffer history, suppressions |
| `SourceHealthMonitor` | `monitor.py` | Stateless: receives current state + accumulated count, evaluates thresholds, returns `HealthAlert` list |

### Why two classes?

`base.py` emits `consecutive_failures` as 0 or 1 (single-run view).
`HealthStore` builds the true running total. `SourceHealthMonitor` is
stateless so threshold logic is trivially unit-testable without any I/O.

---

## P1 Source Registry

8 P1 connector sources are monitored (I4 is a derived helper, no connector):

| ID | Name | Category | Integration |
|----|------|----------|-------------|
| F1 | NPPES NPI Registry | federal | REST_API |
| F2 | OIG LEIE Exclusion Database | federal | BULK_DOWNLOAD |
| F3 | SAM.gov Exclusions | federal | REST_API |
| F4 | CMS Care Compare | federal | REST_API |
| I1 | CMS Medicare Enrollment | federal | REST_API |
| I2 | CMS Medicaid Enrollment | federal | REST_API |
| A1 | PubMed / NCBI Entrez | academic | REST_API |
| A2 | ClinicalTrials.gov | academic | REST_API |

All 8 are pre-seeded as `UNKNOWN` on startup (mirroring the Aurora 0003+0004 seed rows).

---

## Alert Types

| Alert Type | Threshold | Severity |
|------------|-----------|----------|
| `CONSECUTIVE_FAILURES` | `>= 3` runs | WARNING |
| `CONSECUTIVE_FAILURES` | `>= 5` runs | CRITICAL |
| `SCHEMA_DRIFT` | `schema_drift_detected == True` | WARNING |
| `STALE_SOURCE` | `last_successful > 4h ago` (API) or `48h ago` (bulk) | WARNING |
| `LOW_RECORD_COUNT` | `bulk_record_count < expected_min` (bulk only) | WARNING |
| `AUTH_FAILURE` | `status == AUTHENTICATION_FAILED` | CRITICAL |

All thresholds are configurable via `MonitorSettings` / env vars.

---

## REST API

```
GET  /healthz                              Service liveness
GET  /readyz                               Readiness (reports db_configured)
GET  /v1/sources                           FleetHealthSummary (all 8 sources)
GET  /v1/sources/{source_id}              SourceHealthSummary + recent history
GET  /v1/sources/{source_id}/history      Full history (ring buffer, newest first)
GET  /v1/alerts                            AlertsResponse (active + suppressed counts)
POST /v1/sources/{source_id}/ingest       Accept SourceHealthRecord from adapter run
POST /v1/sources/{source_id}/suppress     Suppress alerts for a source until datetime
```

Interactive docs at `/docs` when running locally.

---

## Running locally

```bash
make run-monitor
# => http://localhost:8002/docs
```

---

## Testing

```bash
PYTHONPATH=src pytest tests/backend/test_source_health_monitor.py -v
PYTHONPATH=src pytest tests/data/test_source_health_history.py -v
```

---

## Production notes (deferred until Entry 003)

- **Current state** persisted via Aurora upsert on `source_health_records` (migration 0001).
- **History** appended to `source_health_history` (migration 0004).
- **Prometheus metrics** (`source_consecutive_failures`,
  `source_last_successful_run_age_seconds`) exported from the `/metrics` endpoint
  or OTel gauge; scraped by the 1-D ServiceMonitor (`servicemonitors.yaml`).
- **Active probe mode** (Phase 3-K): the 2-C MVP only ingests records via push
  from adapter workers. Phase 3-K adds scheduled pull probes that run adapters on a cron.
