# Identity Resolution Engine (C12) -- Phase 2-E

**Component:** C12  
**Phase:** 2-E  
**Pattern:** Pure in-memory library (same as `src/normalizers/`)  
**No network I/O. No deployed service. No state beyond the injected IdentityStore.**

---

## What This Does

Takes `NormalizedRecord` objects (C11 output, all P1 federal sources) and builds
`UnifiedIdBundle` objects -- one bundle per NPI. The bundle is the system's best
determination that all data collected for a given `primary_npi` belongs to a single
real-world provider.

**Input:** `NormalizedRecord` subclasses with `entity_npi` set (guaranteed by C11)  
**Output:** `UnifiedIdBundle` objects (mapped to `unified_id_bundles` table in migration 0001)

---

## Matching Strategy (MVP)

**NPI-exact-match only.** All C11-normalized P1 records have `entity_npi` set.
The NPI is the lookup key. No probabilistic matching in Phase 2-E.

Probabilistic ML matching (Splink) is deferred to Phase 3-I.

---

## Confidence Model (DECISIONS.md Entry 026)

```
F1 (NPPES, the NPI registry itself) present:
  base = 0.950

  Per NPI-corroborating source (NPI always from raw payload: F4, I1, I2):
    + 0.015

  F2 (NPI may be from raw OR caller-supplied entity_npi):
    + 0.005

  F3, A1, A2 (NPI always from caller-supplied entity_npi):
    + 0.000 (no confidence boost)

  Cap: min(score, 0.999)

F1 absent:
  max = 0.750, human_review_required = True

human_review_required: confidence < 0.850 (configurable)
```

Key milestones:

| Sources          | Confidence | Notes                              |
|------------------|------------|------------------------------------|
| F1               | 0.950      | NPPES alone (base)                 |
| F1 + F4          | 0.965      |                                    |
| F1 + F4 + I1     | **0.980**  | >= architecture target (>0.98)     |
| F1 + F4 + I1 + I2| 0.995      | All Medicare/Medicaid enrollment   |
| No F1            | max 0.750  | Always flags human review          |

---

## Module Layout

```
src/identity/
  __init__.py      Public API (IdentityResolver, IdentityStore, ConfidenceScorer, models)
  config.py        IdentitySettings (all thresholds configurable via env vars)
  confidence.py    ConfidenceScorer -- stateless; source-tier model
  models.py        ResolutionResult, ResolutionAction, BatchResolutionSummary
  store.py         IdentityStore -- in-memory bundle store (Aurora-backed at deploy)
  resolver.py      IdentityResolver -- resolve() + resolve_batch()
  README.md        This file
```

---

## Usage

```python
from identity import IdentityResolver

resolver = IdentityResolver()

# Single record
result = resolver.resolve(nppes_normalized_record)
print(result.action)           # ResolutionAction.CREATED
print(result.confidence_after) # 0.950

# Batch (F1 records are processed first automatically)
summary = resolver.resolve_batch([f4_record, f1_record, i1_record])
print(summary.created)   # 1
print(summary.merged)    # 2

# Inspect the store
bundle = resolver.store.get("1234567890")
print(bundle.identity_confidence)   # 0.980 after F1+F4+I1
print(bundle.contributing_sources)  # ['F1', 'F4', 'I1']
```

---

## F1 as Identity Anchor

When F1 (NppesRecord) is the first record for an NPI:
- Full identity extracted: name, entity_type, addresses, taxonomies, other_identifiers.

When F1 arrives for a bundle seeded by another source:
- F1 upgrades primary_name, entity_type, addresses, taxonomies.
- Prior stub primary_name is preserved as a name_variant (if non-trivial and different).

When F1 is never seen (non-F1 first record):
- Minimal stub created: best-available name hint (OigLeieRecord has first/last),
  entity_type=INDIVIDUAL default, `human_review_required=True`.

---

## Idempotency

Resolving a source_id that is already in `contributing_sources` returns
`ResolutionAction.SKIPPED` and leaves the bundle unchanged. Guards against
re-processing the same ingest batch.

---

## Deferred (not in MVP)

- Aurora-backed IdentityStore (deferred to DECISIONS.md Entry 003 resolution)
- Probabilistic name matching (Splink ML) -- Phase 3-I
- Gender extraction from F1 basic.gender -- deferred to C13
- Thread-safe concurrent resolution (Temporal worker concurrency -- Phase 2-H)
- Per-NPI row lock (Aurora `SELECT ... FOR UPDATE`) -- Phase 2-H

---

## Testing

```bash
make identity-test
# or
PYTHONPATH=src pytest tests/identity/ -v
```

715 + 45 = **760 tests** after Phase 2-E (no DB required, all synchronous).
