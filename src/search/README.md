# Provider Search Library (`src/search/`)

**Component:** C14 — Provider Search Service  
**Phase:** 2-G  
**Pattern:** Pure library + FastAPI shell (same as C12 identity, C13 entity_linker)  
**DECISIONS.md:** Entry 028

---

## Purpose

Sits between the Entity Linking & Merge output (C13) and the report request flow.
Provides two capabilities:

1. **Indexing** — converts a `CanonicalProviderProfile` into an OpenSearch document
   and writes it to the `providers-{env}` index (template from Phase 1-C).
2. **Search** — serves NPI exact-lookup and name/specialty fuzzy search over that index
   via the FastAPI shell at `src/backend/search_service/`.

---

## Module map

| File | Purpose |
|------|---------|
| `config.py` | `SearchSettings` — env-driven config (prefix `SEARCH_`) |
| `models.py` | `ProviderDoc` (index document), `SearchRequest/Response`, `ProviderSearchHit`, `IndexResult/BatchIndexResult` |
| `document.py` | `build_provider_doc(profile) -> ProviderDoc` — pure, no I/O |
| `query.py` | `build_npi_query()`, `build_search_query()` — pure Query DSL builders |
| `client.py` | `OpenSearchClient` — thin httpx wrapper (`index_doc`, `bulk_index`, `search`, `get_doc`) |
| `indexer.py` | `ProviderIndexer` — coordinates build_provider_doc + client write |

---

## Local dev

```bash
# Start OpenSearch
docker compose -f docker-compose.dev.yml up opensearch -d

# Apply index template (one-time)
curl -X PUT http://localhost:9200/_index_template/providers-template \
  -H 'Content-Type: application/json' \
  -u admin:DevOpenSearch1! \
  -d @src/data/opensearch/providers_index_template.json

# Start the search service (port 8003)
make run-search-service
# curl http://localhost:8003/healthz
# curl 'http://localhost:8003/v1/providers/search?q=Smith&state=CA'
# curl http://localhost:8003/v1/providers/1234567890

# Run tests (no OpenSearch needed)
make search-test
```

---

## Key design choices (Entry 028)

- **Library pattern.** No network I/O in `document.py` or `query.py`. The `OpenSearchClient`
  is injected so tests mock it directly — no HTTP fixtures needed.
- **httpx over opensearch-py.** Avoids a new dependency; the REST API surface used is minimal.
- **NPI as document `_id`.** `client.index_doc(doc_id=profile.npi)` — avoids a separate
  lookup table; `GET /{index}/_doc/{npi}` is an O(1) fetch.
- **function_score boost.** `identity_confidence` (field_value_factor, 1.5×) promotes
  verified providers above partial stubs for the same text match.
- **`report_count = 0` always.** The counter is not yet wired. Phase 2-J (Stripe + report
  pipeline) will increment it via Aurora.
- **All list fields sorted.** Stable, deterministic output for identical profiles.

---

## Blockers

- Live OpenSearch cluster: blocked by DECISIONS.md Entry 003 (AWS account/region).
- `overall_risk_score` signal: always 0.0 until C16 (Phase 2-J Analytics & Anomaly Detection).
- `report_count`: always 0 until Phase 2-J wires the counter.
