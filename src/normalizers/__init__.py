"""
normalizers -- C11 Normalization Layer (Phase 2-D).

Transforms RawRecord objects (C10 connector output) into typed NormalizedRecord
subclasses. This is a pure transformation library: no network I/O, no deployed
service, no state. Normalizers run as part of the ingest pipeline (later: as
Temporal activities in C15).

Public API
----------
    from normalizers import normalize, get_normalizer, NormalizationError

    # Normalize a single RawRecord for a known source:
    record = normalize(raw_record, entity_npi="1234567890")

    # Or retrieve the normalizer instance directly:
    normalizer = get_normalizer("F1")
    record = normalizer.normalize(raw_record)

    # For A1/A2/F3 (no NPI in raw), supply entity_npi:
    record = normalize(raw_record, entity_npi="1234567890")

    # The specialty-group helper (I4 crosswalk via F1):
    from normalizers.sources import get_specialty_group
    sg = get_specialty_group(nppes_record)   # -> "Allopathic & Osteopathic Physicians" | None

DECISIONS.md Entry 025.
LEGAL GATE: ingestion is governed by the Phase 0 FCRA determination.
"""
from __future__ import annotations

# Import sources package to trigger all @register decorators.
# This must happen before any call to get_normalizer().
import normalizers.sources as _sources  # noqa: F401

from .base import NormalizationError as NormalizationError
from .base import SourceNormalizer as SourceNormalizer
from .registry import get_normalizer as get_normalizer
from .registry import registered_source_ids as registered_source_ids
from connectors.models import RawRecord
from schema.v1.normalized import NormalizedRecord


def normalize(raw: RawRecord, *, entity_npi: str | None = None) -> NormalizedRecord:
    """
    Normalize a RawRecord using the registered normalizer for raw.source_id.

    Convenience wrapper around get_normalizer(raw.source_id).normalize(raw, ...).
    Raises NormalizationError if no normalizer is registered or normalization fails.
    """
    normalizer = get_normalizer(raw.source_id)
    return normalizer.normalize(raw, entity_npi=entity_npi)


# Expose the 8 registered P1 source IDs as a constant for tests / config.
P1_NORMALIZER_SOURCE_IDS: list[str] = ["F1", "F2", "F3", "F4", "I1", "I2", "A1", "A2"]
