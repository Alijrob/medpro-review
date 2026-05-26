"""
entity_linker -- Entity Linking & Merge MVP (C13, Phase 2-F).

Builds CanonicalProviderProfile objects from a resolved UnifiedIdBundle
and all contributing NormalizedRecords for a given NPI.

Public API::

    from entity_linker import EntityLinker, LinkerSettings, MergeResult

    linker = EntityLinker()
    result: MergeResult = linker.build_profile(bundle, records)
    profile = result.profile  # CanonicalProviderProfile

DECISIONS.md Entry 027.
"""

from .config import LinkerSettings
from .merger import EntityLinker
from .models import MergeResult, RecordTypeCounts
from .signals import COMPLETENESS_WEIGHTS, compute_derived_signals

__all__ = [
    "EntityLinker",
    "LinkerSettings",
    "MergeResult",
    "RecordTypeCounts",
    "COMPLETENESS_WEIGHTS",
    "compute_derived_signals",
]
