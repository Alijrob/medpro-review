"""
identity -- C12 Identity Resolution Engine (Phase 2-E).

Pure in-memory library that groups NormalizedRecord objects (C11 output) into
UnifiedIdBundle objects. No network I/O, no deployed service, no state beyond
the injected IdentityStore.

Public API
----------
    from identity import IdentityResolver, IdentityStore, ConfidenceScorer
    from identity.models import ResolutionResult, ResolutionAction, BatchResolutionSummary
    from identity.config import IdentitySettings

    # Default resolver with a fresh in-memory store:
    resolver = IdentityResolver()
    result = resolver.resolve(normalized_record)       # single record
    summary = resolver.resolve_batch(records_list)     # batch (F1-first ordering)

    # Inspect the store after resolution:
    bundle = resolver.store.get("1234567890")
    all_bundles = resolver.store.get_all()

    # Score confidence directly:
    scorer = ConfidenceScorer()
    conf = scorer.score(["F1", "F4", "I1"])            # -> 0.980

NPI routing contract (inherited from C11):
    F1 NPPES / F4 CMS Care Compare / I1 Medicare / I2 Medicaid:
        entity_npi extracted from raw -- always set by C11 normalizer.
    F2 OIG LEIE:
        entity_npi from raw["NPI"] when present (post-2008 exclusions);
        falls back to caller-supplied entity_npi (pre-2008 exclusions).
    F3 SAM.gov / A1 PubMed / A2 ClinicalTrials.gov:
        entity_npi always caller-supplied; never in raw.

Confidence model: DECISIONS.md Entry 026.
Legal gate: governs live ingestion (Phase 0 FCRA determination).
"""
from __future__ import annotations

from .confidence import ConfidenceScorer as ConfidenceScorer
from .config import IdentitySettings as IdentitySettings
from .models import (
    BatchResolutionSummary as BatchResolutionSummary,
    ResolutionAction as ResolutionAction,
    ResolutionResult as ResolutionResult,
)
from .resolver import IdentityResolver as IdentityResolver
from .store import IdentityStore as IdentityStore

__all__ = [
    "IdentityResolver",
    "IdentityStore",
    "ConfidenceScorer",
    "IdentitySettings",
    "ResolutionResult",
    "ResolutionAction",
    "BatchResolutionSummary",
]
