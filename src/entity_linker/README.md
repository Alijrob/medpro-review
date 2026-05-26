# Entity Linking & Merge (C13) — Phase 2-F

`src/entity_linker/` is the **Entity Linking & Merge MVP** for the medpro-review platform.

It takes the output of C12 (Identity Resolution) — a `UnifiedIdBundle` — plus all
contributing `NormalizedRecord` objects for that NPI, and produces a single
`CanonicalProviderProfile` ready for report generation (C17, Phase 2-I).

---

## What it does

| Input | Output |
|-------|--------|
| `UnifiedIdBundle` (C12 output) | `CanonicalProviderProfile` (schema v1) |
| `list[NormalizedRecord]` (C11 output) | `MergeResult` (profile + metadata) |

1. **Routes** each `NormalizedRecord` to its per-type extractor by `record_type` discriminator.
2. **Extracts** sub-models (ExclusionRecord, HospitalAffiliation, InsuranceParticipation, PublicationSummary).
3. **Calls `get_specialty_group()`** from the F1 normalizer (I4 crosswalk) to resolve the specialty group string.
4. **Computes four derived signals**: `exclusion_flag`, `identity_confidence`, `specialty_classification`, `data_completeness`.
5. **Calculates** `report_completeness_score` and sets `is_partial`.
6. **Tracks** source coverage per `SourceCategory`.
7. Returns a **`MergeResult`** with the finished profile + per-call metadata.

---

## Architecture

```
src/entity_linker/
  __init__.py        # Public API: EntityLinker, LinkerSettings, MergeResult
  config.py          # LinkerSettings (pydantic-settings, env prefix LINKER_)
  extractors.py      # Per-record-type pure extraction functions
  signals.py         # Derived signal builders + COMPLETENESS_WEIGHTS
  merger.py          # EntityLinker.build_profile() — main entry point
  models.py          # MergeResult, RecordTypeCounts
  README.md          # This file
```

**Library pattern** (same as `src/normalizers/`, `src/identity/`): no network, no DB, no side effects.
Will run as Temporal activities in Phase 2-H.

---

## Usage

```python
from entity_linker import EntityLinker

linker = EntityLinker()
result = linker.build_profile(bundle, records)

profile = result.profile          # CanonicalProviderProfile
sg = result.specialty_group       # "Family Medicine" | None
counts = result.record_counts     # RecordTypeCounts
```

### Configuration via environment

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKER_MAX_RECENT_PUBLICATIONS` | `10` | Cap on `recent_publications` list |
| `LINKER_COMPLETENESS_THRESHOLD_FOR_PARTIAL` | `0.70` | Below this, `is_partial = True` |

---

## Derived signals

| signal_type | value | confidence | note |
|-------------|-------|-----------|------|
| `exclusion_flag` | 1.0 (excluded) / 0.0 | 0.95 if F2/F3 checked | ALERT when 1.0 |
| `identity_confidence` | 0.0–1.0 (mirrors bundle) | same as value | high ≥0.98 |
| `specialty_classification` | 1.0 (known) / 0.0 | 0.95 with F1 | resolves via I4 crosswalk |
| `data_completeness` | 0.0–1.0 (weighted) | same as value | see COMPLETENESS_WEIGHTS |

### Completeness weights (COMPLETENESS_WEIGHTS)

| Section | Weight | Trigger |
|---------|--------|---------|
| identity_anchor | 0.30 | F1 in contributing_sources |
| exclusion_checked | 0.20 | F2 or F3 in contributing_sources |
| medicare_status | 0.15 | I1 in contributing_sources |
| address_present | 0.10 | >= 1 known address in bundle |
| hospital_affiliation | 0.10 | F4 in contributing_sources |
| medicaid_status | 0.08 | I2 in contributing_sources |
| publications_checked | 0.04 | A1 in contributing_sources |
| clinical_trials_checked | 0.03 | A2 in contributing_sources |

F1 + F2 + I1 + F4 = 0.30 + 0.20 + 0.15 + 0.10 = **0.75** — enough for `is_partial = False` at default threshold.

---

## Tests

```
make entity-linker-test
```

109 unit tests (0 network, 0 DB):
- `test_extractors.py` — per-extractor tests (OIG, SAM, CMS, Medicare, Medicaid, PubMed)
- `test_signals.py` — per-signal tests + COMPLETENESS_WEIGHTS invariants
- `test_merger.py` — EntityLinker.build_profile() with various record combinations
- `test_entity_linker_integration.py` — end-to-end multi-source bundle assembly

---

## Deferred / open

- **Aurora persistence** (`canonical_provider_profiles` table, migration 0001): deferred to Entry 003.
- **State-board records** (StateBoardLicenseRecord, StateBoardDisciplinaryRecord): Phase 3-A adds extractor functions and adds their `record_type` strings to `_BUCKET_MAP`.
- **Court records** (CourtCaseRecord): Phase 3-C.
- **Review platform records** (ReviewPlatformRecord): Phase 3-E.
- **Gender extraction from F1**: NppesRecord does not carry gender (deferred from C11); `profile.gender` mirrors `bundle.gender` (always `UNKNOWN` until C11 extracts `basic.gender` from NPPES).
- **A1/A2 author_position disambiguation**: `author_position` is None in C11; deferred to this phase for enrichment — but NPPES NPI lookup on author list is out of scope until Phase 3.
- **`is_partial` lifecycle**: Phase 2-H Temporal workflow will track sources attempted vs succeeded at the workflow level and update `is_partial` when the full cycle completes.

DECISIONS.md Entry 027.
