# Session Summary: 2026-05-26 -- Phase 2-F Complete (Entity Linking & Merge MVP)

**Date:** 2026-05-26
**Session goal:** Build Phase 2-F: Entity Linking & Merge MVP (component C13).

---

## Summary (readable cold)

This session built the Entity Linking & Merge Engine (C13), a pure in-memory library at
`src/entity_linker/` that is the final pre-report-generation step in the provider data
pipeline. It takes a `UnifiedIdBundle` (C12 output) and all contributing
`NormalizedRecord` objects for a given NPI and assembles a `CanonicalProviderProfile`
(schema v1) -- the read model that report generation (C17, Phase 2-I) will consume.

The library follows the same library pattern as `src/normalizers/` and `src/identity/`:
no network I/O, no DB writes, no side effects. All routing is done by `record_type`
discriminator (not isinstance checks), making it extensible: adding Phase 3 state-board
or court records requires one line in `_BUCKET_MAP` and a new extractor function.

The central function `EntityLinker.build_profile(bundle, records)` calls per-type
extractor functions (OIG/SAM exclusions, CMS hospital affiliations and practice context,
Medicare/Medicaid participation, PubMed publications), calls `get_specialty_group()` from
the F1 normalizer (I4 crosswalk), computes 4 derived signals (exclusion_flag,
identity_confidence, specialty_classification, data_completeness), calculates a weighted
`report_completeness_score` from the `COMPLETENESS_WEIGHTS` rubric (8 sections, sum=1.0),
and returns a `MergeResult` wrapping the finished profile.

The `report_disclaimer_required=True` field is always set (Path B non-CRA constraint). The
`is_partial` flag is True when completeness < 0.70 or `human_review_required` is True.
Gender pass-through from the bundle (always UNKNOWN until C11 adds `basic.gender`
extraction from NPPES). 109 new tests (885 total). DECISIONS.md Entry 027.

---

## Repo

- Repo: https://github.com/Alijrob/medpro-review
- Tracker (pinned): https://github.com/Alijrob/pagios-ops/blob/d75076f/trackers/medpro-review-phase-tracker.md

---

## Commit SHAs (this session)

| Repo | SHA | Message |
|------|-----|---------|
| medpro-review | 064d55a8ce9547d84aed8bef2efeb563700d12c8 | Phase 2-F: Entity Linking & Merge MVP (C13) -- EntityLinker + extractors + signals + MergeResult; record_type routing; 4 derived signals; COMPLETENESS_WEIGHTS; 109 new tests (885 total) |
| pagios-ops | d75076f | medpro-review: Phase 2-F complete (Entity Linking & Merge MVP; 885 tests; 064d55a) |

---

## Files changed (this session)

**New source files:**
- `src/entity_linker/__init__.py` -- public API: EntityLinker, LinkerSettings, MergeResult, RecordTypeCounts, COMPLETENESS_WEIGHTS, compute_derived_signals (6 exports)
- `src/entity_linker/config.py` -- `LinkerSettings`: max_recent_publications, completeness_threshold_for_partial; env prefix LINKER_
- `src/entity_linker/extractors.py` -- pure extraction functions: extract_oig_exclusions, extract_sam_exclusions, extract_hospital_affiliations, extract_cms_practice_context, extract_medicare_participation, extract_medicaid_participation, extract_publications
- `src/entity_linker/signals.py` -- signal builders: compute_exclusion_flag, compute_identity_confidence, compute_specialty_classification, compute_data_completeness; COMPLETENESS_WEIGHTS dict; compute_derived_signals() composite
- `src/entity_linker/merger.py` -- EntityLinker class; _BUCKET_MAP discriminator routing; _group_records(); _build_source_coverage(); _compute_completeness_score(); build_profile() main entry point
- `src/entity_linker/models.py` -- MergeResult, RecordTypeCounts
- `src/entity_linker/README.md`

**New test files:**
- `tests/entity_linker/__init__.py`
- `tests/entity_linker/_fixtures.py` -- factory functions: make_bundle, make_org_bundle, make_nppes_record, make_oig_record, make_oig_historical, make_sam_record, make_cms_record, make_medicare_record, make_medicaid_record, make_pubmed_record, make_trial_record
- `tests/entity_linker/test_extractors.py` -- 49 tests (per-extractor: OIG, SAM, CMS affiliations, CMS context, Medicare, Medicaid, PubMed)
- `tests/entity_linker/test_signals.py` -- 24 tests (COMPLETENESS_WEIGHTS invariants, per-signal builders, composite builder)
- `tests/entity_linker/test_merger.py` -- 30 tests (identity fields, exclusions, hospital/practice context, Medicare, Medicaid, publications, derived signals, completeness/partial, Path B, record counts)
- `tests/entity_linker/test_entity_linker_integration.py` -- 16 tests (full P1 bundle, active exclusion propagation, publication cap, multi-state Medicaid, gender pass-through)

**New CI / config:**
- `.github/workflows/entity-linker-validate.yml` -- CI for entity linker tests

**Updated:**
- `pyproject.toml` -- `entity_linker` package added
- `Makefile` -- `entity-linker-test` target + .PHONY + help entry
- `DECISIONS.md` -- Entry 027 (Entity Linking & Merge MVP Design)
- `docs/setup/onboarding.md` -- Phase 2-F marked complete; 2-G next; src/entity_linker/ table entries added

---

## Phase status

| Phase | Status |
|-------|--------|
| 2-A Source Connector Framework (C9) | ✅ Complete |
| 2-B Federal Source Adapters (C10) | ✅ Complete (all 9 P1 sources) |
| 2-C Source Health Monitor MVP (C24) | ✅ Complete |
| 2-D Normalization Layer MVP (C11) | ✅ Complete |
| 2-E Identity Resolution MVP (C12) | ✅ Complete |
| **2-F Entity Linking & Merge MVP (C13)** | ✅ **COMPLETE** |
| **2-G Provider Search Service** | 🔄 **Up next** |
| 2-H Temporal Workflow - Basic Report Generation | ⏳ Pending |

---

## Next likely step

**Phase 2-G -- Provider Search Service.** Builds the provider search layer that sits
between the entity linker output and the report request flow. Likely deliverables:
- OpenSearch index population from `CanonicalProviderProfile` (NPI keyword, name ngram,
  specialty, address fields)
- FastAPI search service (shell) with `/v1/providers/search` and `/v1/providers/{npi}`
  endpoints
- NPI-direct lookup path (exact match, always fast) and name/specialty fuzzy search
- Connected to the existing OpenSearch index template (shipped in Phase 1-C:
  `src/data/opensearch/providers_index_template.json`)
- Query DSL builder for Phase 2-K frontend integration

---

## Known blockers

1. **Phase 0 legal gate (FCRA determination)** -- governs live ingestion for all C10 adapters. All C11-C13 pipeline code is network-free and safe to build.
2. **AWS account/region (DECISIONS.md Entry 003)** -- PLACEHOLDER everywhere; blocks all deploys. Domain locked: `researchyourdoctor.com` (Entry 008).
3. **I2 `DEFAULT_DATASET_ID`** -- placeholder; must be verified against `data.cms.gov` before first live ingest.
4. **Gender extraction** -- NppesRecord does not carry `basic.gender`; `profile.gender` is always UNKNOWN. Deferred from C11 (Entry 025) and C13 (Entry 027).
5. **A1/A2 `author_position`** -- None in C11; no disambiguation in C13. Deferred.

---

## Verified checks

- `medpro-review` working tree clean at session end (`git status --porcelain` empty).
- `medpro-review` HEAD `064d55a` pushed to origin/main (0 ahead / 0 behind confirmed via `git status -sb`).
- `pagios-ops` HEAD `d75076f` pushed to origin/main (confirmed).
- `PYTHONPATH=src pytest tests/ -m "not integration" -q` => **885 passed, 7 deselected** (verified this session close).
  - 109 new entity linker tests (49 extractors + 24 signals + 30 merger + 16 integration)
  - All prior 776 tests still passing (zero regressions)
- COMPLETENESS_WEIGHTS sum verified: `abs(sum(weights) - 1.0) < 1e-9` asserted in module-level assert; tested in `test_weights_sum_to_one`.
- Path B compliance: `test_report_disclaimer_always_true` asserts `report_disclaimer_required=True` on every profile.
- Specialty group resolved: `test_specialty_group_in_result` asserts "Family Medicine" for taxonomy code 207Q00000X.
- No secrets in committed files (scanned: no API_KEY, SECRET, TOKEN, PASSWORD, DATABASE_URL, PRIVATE_KEY found in diff).

---

## Blocked checks

- No live source endpoints exercised (legal gate + no deploy).
- No live cluster / ArgoCD: all manifests unvalidated against a real cluster.
- No live Aurora DB: `canonical_provider_profiles` table not written to (schema exists in migration 0001; EntityLinker produces Pydantic objects only).
- 7 data integration tests deselected (require live PostgreSQL).
- `CanonicalProviderProfile` -> Aurora persistence unverified (no DB write path exists yet; Phase 2-G/2-H will wire it).

---

## Unverified items

- OpenSearch indexing of the profile -- the index template (`providers_index_template.json`) exists from Phase 1-C but profile population is Phase 2-G.
- `SourceCoverage` `last_refreshed_at` timestamps: set to `utc_now()` at merge time; may not reflect actual adapter run timestamps (those are in SourceHealthRecord, not in the linker input).
- `is_partial` lifecycle: currently set at build time based on completeness score; Phase 2-H Temporal workflow will update it when the full ingest cycle completes.
- Gender: always UNKNOWN; profile.gender field not exercised with real values until C11 adds basic.gender extraction from NPPES raw.
- All `expected_min_records` defaults are None in production config; overrides required before live ingest.

---

## Tests run

```
PYTHONPATH=src pytest tests/ -m "not integration" -q
=> 885 passed, 7 deselected, 2 warnings in 17.65s

PYTHONPATH=src pytest tests/entity_linker/ -q
=> 109 passed in 0.47s (verified at start of session close)

opa test src/policy => PASS 16/16 (no policy changes this session)
```
