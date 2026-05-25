# Session Summary: 2026-05-25 -- Phase 2-B.4 (CMS Care Compare Adapter, F4)

> Fourth concrete source adapter (C10). Phase 2-B now has F1-F4 complete (NPPES,
> OIG LEIE, SAM.gov, CMS Care Compare). Part of the day's work; the day rollup
> is `2026-05-25-session-summary.md`.

---

## Summary (readable cold)

Built the **CMS Care Compare adapter (source F4)** -- the highest-value CMS dataset
for provider report breadth. The "Doctors and Clinicians" national downloadable file
(Physician Compare) on `data.cms.gov` contains NPI-level records for every provider
who has billed Medicare: name, primary specialty, practice address, hospital
affiliations, group practice membership, and the accepts-assignment flag (whether
the provider accepts Medicare's approved amount as full payment). This is the
participation and location layer of the platform -- linking F1's NPI identity anchor
to clinical context, practice location, and Medicare acceptance status.

The adapter uses the **Socrata SODA 2.0 API** (the standard format for all
`data.cms.gov` public datasets): `GET /resource/{dataset_id}.json` with `$limit` +
`$offset` + `$order=:id`. No API key required. Pagination terminates when the
response array is shorter than `$limit` (the Socrata short-page sentinel). The
`dataset_id` is a configurable constructor arg (default: `mj5m-pzi6`) to survive
CMS dataset refreshes without a code change.

The dataset has one row per practice location per NPI -- a provider with five
locations yields five rows with the same NPI. The adapter yields all rows as-is;
C11 normalization (Phase 2-D) groups and deduplicates by NPI. A `SchemaContract`
guards 8 required fields (`npi`, `ind_pac_id`, `last_name`, `first_name`, `pri_spec`,
`assgn`, `cty`, `st`). 17 new tests; 408 total passing (was 391). DECISIONS.md
Entry 018.

---

## Repo + tracker

- Repo: https://github.com/Alijrob/medpro-review
- Tracker: `/root/pagios-ops/trackers/medpro-review-phase-tracker.md` (Phase 2-B section)

---

## Files changed (by area)

- Adapter (2-B.4): `src/connectors/sources/cms_care_compare.py` (new --
  `CmsCareCompareConnector`, `cms_care_compare_config`, `_CMS_REQUIRED_FIELDS`).
- Sources package: `src/connectors/sources/__init__.py` (updated -- F4 exports,
  inventory comment updated to "(built, 2-B.4)").
- Tests: `tests/connectors/test_cms_care_compare.py` (new -- 17 tests).
- Decisions: `DECISIONS.md` Entry 018.
- Docs: `src/connectors/README.md` (F4 row added), `docs/setup/onboarding.md`
  (2-B.4 complete, next step 2-B.5, Important Files table, run-validate count
  updated to 79, phase table updated).

---

## Key design decisions (Entry 018)

- **Socrata SODA 2.0 (REST_API).** The standard CMS `data.cms.gov` API pattern.
  Building to SODA means F4's pagination pattern is reusable for I1, I2, and any
  other `data.cms.gov` dataset.
- **Short-page sentinel termination.** SODA 2.0 returns exactly as many records
  as remain on the last page (never pads). When `len(rows) < $limit`, the source
  is exhausted. Simpler than a separate totalRecords count.
- **`$order=:id`.** Socrata system row ID -- the only guaranteed stable sort key
  for deterministic offset-based pagination across large datasets.
- **Configurable `dataset_id`.** CMS has superseded datasets before. Making the ID
  a constructor arg (with a sensible default) survives a refresh without a code change.
- **One-row-per-location is the intended schema.** The adapter yields all rows;
  C11 groups by NPI. This is the correct separation of concerns.
- **8-field contract.** Guards identity + participation + specialty + location.
  Extra columns pass through without alerting -- CMS adds fields occasionally.

---

## Phase status

- Phase 2-B.4 (CMS Care Compare adapter, F4): COMPLETE.
- Phase 2-B (Federal Source Adapters, C10): IN PROGRESS -- 2-B.5 CMS Medicare
  Enrollment (I1) next.

---

## Next likely step

**Phase 2-B.5 -- CMS Medicare Physician Enrollment (I1):** Medicare participation
and opt-out status. CC0, `data.cms.gov` SODA API (same pattern as F4, different
dataset). The enrollment file includes the opt-out list -- a high-value red flag
signal (providers who have opted out of Medicare cannot bill Medicare for covered
services). T1/L0 open-data; live ingestion stays behind the Phase 0 gate.

---

## Known blockers

1. Phase 0 legal gate (FCRA determination) -- gates live ingestion in all C10 adapters.
2. AWS account/region (Entry 003) -- PLACEHOLDER everywhere; blocks any deploy.
3. No live cluster / Auth0 tenant / DB.

---

## Verified checks

- `PYTHONPATH=src pytest tests/connectors/test_cms_care_compare.py -v` => **17 passed**.
- `PYTHONPATH=src pytest tests/ -m "not integration"` => **408 passed, 7 deselected**
  (44 schema + 20 data + 39 observability + 179 gitops + 47 backend + 21 connectors +
  14 nppes + 12 oig-leie + 15 sam-gov + 17 cms).
- No regressions (was 391 at end of 2-B.3; +17 only).
- Adapter imports cleanly (`from connectors.sources import CmsCareCompareConnector, cms_care_compare_config`).

---

## Unverified items

- Live `data.cms.gov` endpoint not exercised (legal gate + no-network policy).
- `expected_min_records` is None by default; production must override to ~2 000 000.
- `source_record_id` left unset on `RawRecord`; set in C11 normalization (Phase 2-D).
- Actual live `dataset_id` for the current Doctors and Clinicians file should be
  verified against `data.cms.gov/provider-data` before first live ingest.

---

## Tests run

```
PYTHONPATH=src pytest tests/ -m "not integration"
=> 408 passed, 7 deselected
   44 schema | 20 data | 39 observability | 179 gitops | 47 backend | 21 connectors
   | 14 nppes | 12 oig-leie | 15 sam-gov | 17 cms
```
