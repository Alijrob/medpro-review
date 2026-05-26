# Session Summary: 2026-05-26 -- Phase 2-G Complete (Provider Search Service)

**Date:** 2026-05-26
**Session goal:** Build Phase 2-G: Provider Search Service (component C14).

---

## Summary (readable cold)

This session built the Provider Search Service (C14), the layer that sits between the Entity
Linking & Merge output (C13) and the report request flow. The work splits into two parts: a
pure library at `src/search/` and a FastAPI shell at `src/backend/search_service/` on port
8003.

The library follows the same pattern as `src/entity_linker/`, `src/identity/`, and
`src/normalizers/`: no network I/O in isolation, fully testable with a mock client. The
central function `build_provider_doc()` takes a `CanonicalProviderProfile` and maps it to a
`ProviderDoc` whose fields exactly mirror the OpenSearch index template shipped in Phase 1-C
(`src/data/opensearch/providers_index_template.json`). All list fields are sorted for
deterministic output. The `build_search_query()` DSL builder produces a `bool` query with
optional `multi_match` (fuzziness=AUTO, operator=and), filter clauses for state/specialty/
entity_type/exclusion/license, wrapped in a `function_score` that boosts results by
`identity_confidence` (factor=1.5, boost_mode=multiply).

The `OpenSearchClient` is a thin httpx wrapper (no opensearch-py dependency added) with four
operations: `index_doc`, `bulk_index`, `search`, `get_doc`. The `ProviderIndexer` coordinates
the `build_provider_doc` -> client write path for both single and batch indexing.

The FastAPI shell exposes three endpoints: `GET /v1/providers/search` (multi-field text +
filter search), `GET /v1/providers/{npi}` (O(1) exact lookup via `get_doc()`, not a search
query), and `POST /v1/providers/{npi}/index` (index or re-index a full CanonicalProviderProfile).
The service follows the same app-factory + singleton-injection pattern as the source health
monitor. All OpenSearch calls are absorbed by the client layer; routes translate errors to
404/502 without ever re-raising.

108 new tests written (38 document unit tests, 28 query DSL tests, 22 mock-client indexer
tests, 27 FastAPI TestClient route tests). No prior tests broken: 993 total passing, 7
integration-marked deselected.

---

## Repo

- Repo: https://github.com/Alijrob/medpro-review
- Tracker (pinned): https://github.com/Alijrob/pagios-ops/blob/1601b57/trackers/medpro-review-phase-tracker.md

---

## Commit SHAs (this session)

| Repo | SHA | Message |
|------|-----|---------|
| medpro-review | d8a37052bd62de4b5b77888dc683d05d8427ac3f | Phase 2-G: Provider Search Service (C14) -- src/search/ library + FastAPI shell :8003; build_provider_doc; build_search_query DSL + function_score boost; OpenSearchClient httpx; ProviderIndexer single+batch; 108 new tests (993 total) |
| pagios-ops | 1601b57 | medpro-review: Phase 2-G complete (Provider Search Service; 993 tests; d8a3705) |

---

## Files changed (this session)

**New source files:**
- `src/search/__init__.py` -- public API (10 exports): SearchSettings/get_settings, build_provider_doc, build_npi_query, build_search_query, ProviderIndexer, OpenSearchClient, ProviderDoc, SearchRequest/Response, ProviderSearchHit, IndexResult/BatchIndexResult
- `src/search/config.py` -- `SearchSettings`: opensearch_url, index_name, credentials, timeout; env prefix `SEARCH_`; `is_configured` property
- `src/search/models.py` -- `ProviderDoc` (mirrors providers_index_template.json), `SearchFilters`, `SearchRequest`, `SearchResponse`, `ProviderSearchHit`, `IndexResult`, `BatchIndexResult`
- `src/search/document.py` -- `build_provider_doc(profile) -> ProviderDoc`; pure; `_get_signal_value()` helper; all lists sorted
- `src/search/query.py` -- `build_npi_query(npi)`, `build_search_query(q, state, specialty_code, entity_type, has_exclusion, has_active_license, from_offset, page_size)`; `_SEARCH_SOURCE_FIELDS` projection
- `src/search/client.py` -- `OpenSearchClient`: httpx.Client auth/timeout; `IndexRawResponse`, `BulkRawResponse`, `SearchRawResponse`, `GetRawResponse` dataclasses; `index_doc`, `bulk_index`, `search`, `get_doc`
- `src/search/indexer.py` -- `ProviderIndexer(index_name)`; `index_profile(profile, client) -> IndexResult`; `index_batch(profiles, client) -> BatchIndexResult`; per-item error parsing
- `src/search/README.md`
- `src/backend/search_service/__init__.py`
- `src/backend/search_service/app.py` -- `create_app()` factory; Sentry/OTel best-effort; wires client + indexer singletons
- `src/backend/search_service/routes.py` -- `_set_singletons()`; `GET /healthz`, `GET /readyz`, `GET /v1/providers/search`, `GET /v1/providers/{npi}`, `POST /v1/providers/{npi}/index`

**New test files:**
- `tests/search/__init__.py`
- `tests/search/_fixtures.py` -- `make_minimal_profile`, `make_full_profile`, `make_excluded_profile`, `make_org_profile`, `make_no_address_profile`; signal/address/taxonomy helpers
- `tests/search/test_document.py` -- 38 tests: basic field mapping, primary_name keys, name_variants dedup/sort, address facets, specialty, taxonomy descriptions, signal extraction, boolean flags, source coverage count, gender, org profile, determinism
- `tests/search/test_query.py` -- 28 tests: NPI query structure, function_score, match_all vs multi_match, all filter types, combined filters, pagination, _source fields
- `tests/search/test_indexer.py` -- 22 tests: index_profile success/failure, doc_id=NPI, body contains primary_npi, batch empty/all-success/partial-failure/all-fail-empty-items
- `tests/backend/test_search_service.py` -- 27 tests: healthz, readyz not_configured (empty URL), search 200/envelope/hits/pagination/query_body/state_filter, NPI lookup found/404/source_none/invalid_format/short, index_provider 201/mismatch_422/client_failure_502

**New CI:**
- `.github/workflows/search-validate.yml` -- triggers on src/search/, src/backend/search_service/, tests/search/, tests/backend/test_search_service.py, pyproject.toml

**Updated:**
- `pyproject.toml` -- `search` package added to packages list
- `Makefile` -- `run-search-service` (port 8003) + `search-test` targets; .PHONY updated
- `DECISIONS.md` -- Entry 028 (Provider Search Service Design)
- `docs/setup/onboarding.md` -- Phase 2-G COMPLETE added; Phase 2-H next; src/search/ table entries added

---

## Phase status

| Phase | Status |
|-------|--------|
| 2-A Source Connector Framework (C9) | ✅ Complete |
| 2-B Federal Source Adapters (C10) | ✅ Complete (all 9 P1 sources) |
| 2-C Source Health Monitor MVP (C24) | ✅ Complete |
| 2-D Normalization Layer MVP (C11) | ✅ Complete |
| 2-E Identity Resolution MVP (C12) | ✅ Complete |
| 2-F Entity Linking & Merge MVP (C13) | ✅ Complete |
| **2-G Provider Search Service (C14)** | ✅ **COMPLETE** |
| **2-H Temporal Workflow - Basic Report Generation** | 🔄 **Up next** |
| 2-I Report Generation MVP (JSON + HTML) | ⏳ Pending |
| 2-J Payment Service MVP (Stripe Checkout) | ⏳ Pending |
| 2-K Frontend Phase 1 | ⏳ Pending |

---

## Next likely step

**Phase 2-H -- Temporal Workflow + Basic Report Generation.** Likely deliverables:
- Temporal worker that orchestrates the full per-NPI pipeline: source adapters (C10) ->
  normalizers (C11) -> identity resolver (C12) -> entity linker (C13) -> search indexer (C14)
- Temporal activities wrapping each library (all are pure in-memory; wire them as activities)
- `last_full_refresh_at` and `is_partial=False` lifecycle: set when all source adapters
  complete for a given NPI
- Basic report generation (C17): JSON report from CanonicalProviderProfile + HTML template

---

## Known blockers

1. **AWS account/region (Entry 003)** -- PLACEHOLDER everywhere in Terraform; blocks all deploys, Aurora persistence, live OpenSearch cluster, live Redis.
2. **FCRA legal gate (Phase 0)** -- governs live source ingestion for all C10 adapters. All C11-C14 pipeline code is network-free and safe to build.
3. **`TEMPORAL_ADDRESS` not provisioned** -- Temporal cluster needed before Phase 2-H workflow can run end-to-end.
4. **`overall_risk_score` signal** -- always 0.0 in ProviderDoc until C16 (Phase 2-J Analytics) is built.
5. **`report_count`** -- always 0 until Phase 2-J Stripe + report pipeline wires the counter.

---

## Verified checks

- `medpro-review` working tree clean at session end (`git status --porcelain` empty).
- `medpro-review` HEAD `d8a3705` pushed to origin/main (0 ahead / 0 behind confirmed).
- `pagios-ops` HEAD `1601b57` pushed to origin/main (confirmed).
- `PYTHONPATH=src pytest tests/ -m "not integration" -q` => **993 passed, 7 deselected** (verified at session close).
  - 108 new search + search_service tests
  - All prior 885 tests still passing (zero regressions)
- `build_provider_doc()` purity: no network call in any of the 38 document tests (mock-free).
- `build_search_query()` DSL contract: all 5 filter types tested independently and in combination.
- `ProviderIndexer.index_batch()` partial failure path: per-item error parsing verified (test_indexer.py).
- Gender enum values corrected: `Gender.FEMALE.value == "F"`, `Gender.UNKNOWN.value == "U"` (single-letter codes per federal registry convention).
- No secrets in committed files (scanned: no API_KEY, SECRET, TOKEN, PASSWORD, DATABASE_URL, PRIVATE_KEY).
- CI workflow `.github/workflows/search-validate.yml` committed and pushed.

---

## Blocked checks

- No live OpenSearch cluster exercised (Entry 003 blocks all infra).
- No live Aurora DB: `canonical_provider_profiles` Aurora persistence not tested.
- No Temporal workflow: Phase 2-H will wire the library activities.
- 7 data integration tests deselected (require live PostgreSQL).

---

## Unverified items

- OpenSearch `function_score` query execution: DSL structure verified by unit tests; actual ranking boost unverified without a live cluster.
- `POST /v1/providers/{npi}/index` end-to-end with real OpenSearch: not testable until Entry 003.
- `index_batch` with a real bulk API response structure: mock matches documented OpenSearch bulk response shape but unverified against a live cluster.
- CI `.github/workflows/search-validate.yml` execution: pushed to GitHub but workflow has not yet been triggered by a pull request.

---

## Tests run

```
PYTHONPATH=src pytest tests/ -m "not integration" -q
=> 993 passed, 7 deselected, 5 warnings in 18.92s

PYTHONPATH=src pytest tests/search/ tests/backend/test_search_service.py -v -q
=> 108 passed in 1.10s (verified at session close)
```
