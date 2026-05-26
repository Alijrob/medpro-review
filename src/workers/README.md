# workers -- C15 Temporal Worker (Phase 2-H basic)

Temporal worker that orchestrates the full per-NPI provider data pipeline.

## Pipeline

```
ProviderPipelineWorkflow(npi)
  1. fan-out: fetch_source_activity x N sources (parallel)
  2. normalize_records_activity (all raw records)
  3. resolve_identity_activity  -> UnifiedIdBundle
  4. link_and_merge_activity    -> CanonicalProviderProfile
  5. index_profile_activity     -> OpenSearch (best-effort)
  6. generate_report_activity   -> ProviderReport + HTML
```

## Files

| File | Purpose |
|------|---------|
| `config.py` | `WorkerSettings` (env prefix `WORKER_`); `P1_SOURCE_IDS` |
| `models.py` | Temporal I/O models (Pydantic, JSON-serialisable) |
| `activities/fetch.py` | `fetch_source_activity` -- C10 connector wrapper |
| `activities/normalize.py` | `normalize_records_activity` -- C11 normalizer wrapper |
| `activities/resolve.py` | `resolve_identity_activity` -- C12 identity resolver wrapper |
| `activities/link.py` | `link_and_merge_activity` -- C13 entity linker wrapper |
| `activities/index.py` | `index_profile_activity` -- C14 search indexer wrapper |
| `activities/generate_report.py` | `generate_report_activity` -- C17 report builder wrapper |
| `workflows/provider_pipeline.py` | `ProviderPipelineWorkflow` |
| `worker.py` | Worker entrypoint |

## Running the worker

```bash
# Dev (no live Temporal -- for testing only)
WORKER_TEMPORAL_ADDRESS=localhost:7233 python -m workers.worker

# Or via Makefile:
make run-worker
```

## Testing activities

Activities are plain Python functions decorated with `@activity.defn`.
They can be called directly in tests:

```python
from workers.activities import normalize_records_activity
from workers.models import NormalizeRecordsInput

inp = NormalizeRecordsInput(raw_records=[...], entity_npi="1234567890")
out = normalize_records_activity(inp)  # no Temporal server needed
```

## Env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `WORKER_TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server |
| `WORKER_TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `WORKER_TEMPORAL_TASK_QUEUE` | `medpro-provider-pipeline` | Task queue |
| `WORKER_FETCH_ACTIVITY_TIMEOUT_S` | `300` | Per-source fetch timeout |
| `WORKER_NORMALIZE_ACTIVITY_TIMEOUT_S` | `60` | Normalization timeout |
| `WORKER_RESOLVE_ACTIVITY_TIMEOUT_S` | `30` | Identity resolution timeout |
| `WORKER_LINK_ACTIVITY_TIMEOUT_S` | `60` | Entity linking timeout |
| `WORKER_INDEX_ACTIVITY_TIMEOUT_S` | `30` | OpenSearch index timeout |
| `WORKER_REPORT_ACTIVITY_TIMEOUT_S` | `30` | Report generation timeout |

## DECISIONS.md

Entry 029 -- Temporal Workflow Design (Phase 2-H)
