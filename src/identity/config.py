"""
config.py -- IdentitySettings for the C12 Identity Resolution Engine (Phase 2-E).

All thresholds and source-tier assignments are configurable here so the scoring
model can be tuned without touching algorithm code.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings


class IdentitySettings(BaseSettings):
    """
    Runtime settings for the Identity Resolution Engine.

    All values have safe defaults for local development and unit tests.
    Override via environment variables (prefix: IDENTITY_) in deployed environments.
    """

    # --- Confidence thresholds ---

    # Confidence assigned to a bundle seeded by F1 alone (NPPES is the NPI registry itself).
    f1_base_confidence: float = 0.950

    # Confidence boost per NPI-corroborating source (NPI always in raw payload: F4, I1, I2).
    # Three such sources brings F1-seeded confidence above the 0.980 architecture target.
    npi_corroborating_boost: float = 0.015

    # Confidence boost for F2 (OIG LEIE): NPI may be from raw OR from caller-supplied entity_npi.
    # Smaller boost than fully-corroborating sources due to the ambiguity.
    npi_partial_boost: float = 0.005

    # Maximum confidence cap (never quite 1.0 -- MVP cannot fully eliminate all uncertainty).
    max_confidence: float = 0.999

    # Maximum confidence when F1 is not present (NPI not verified by the registry itself).
    no_f1_max_confidence: float = 0.750

    # Per-additional-source increment when F1 is absent (weak corroboration without anchor).
    no_f1_per_source: float = 0.010

    # Bundles below this threshold are flagged for human review.
    human_review_threshold: float = 0.850

    # --- Source tier assignments ---

    # The single NPI-authoritative source (the NPI registry itself).
    npi_authoritative_sources: frozenset[str] = frozenset({"F1"})

    # Sources whose raw payload always contains an independently-issued NPI
    # (not caller-supplied entity_npi). Each raises confidence by npi_corroborating_boost.
    npi_corroborating_sources: frozenset[str] = frozenset({"F4", "I1", "I2"})

    # Sources whose raw payload may contain NPI (F2 OIG LEIE: pre-2008 exclusions have no NPI,
    # post-2008 have NPI in raw; C11 normalizer falls back to entity_npi when raw is empty).
    # Scored with npi_partial_boost because the NPI source is ambiguous.
    npi_partial_sources: frozenset[str] = frozenset({"F2"})

    # Sources that never carry NPI in their raw payload; always caller-supplied entity_npi.
    # These add to contributing_sources but do not raise identity_confidence.
    npi_caller_sources: frozenset[str] = frozenset({"F3", "A1", "A2"})

    model_config = {"env_prefix": "IDENTITY_", "frozen": True}
