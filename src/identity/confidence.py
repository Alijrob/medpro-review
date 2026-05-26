"""
confidence.py -- ConfidenceScorer for the C12 Identity Resolution Engine.

Assigns identity_confidence to a UnifiedIdBundle based on which sources have
contributed to it. The model is deterministic and stateless: given the same
set of contributing_sources, it always returns the same score.

Confidence model (DECISIONS.md Entry 026):
------------------------------------------

  F1 present (NPPES, the NPI registry itself):
    base = 0.950

  F1 absent:
    max = 0.750, human_review_required = True
    (NPI not independently verified by the registry)

  Per NPI-corroborating source (F4, I1, I2 -- NPI always from raw):
    +0.015 per source

  F2 (OIG LEIE -- NPI may be from raw OR caller-supplied entity_npi):
    +0.005 (partial boost; ambiguity about NPI provenance)

  F3, A1, A2 (NPI always from caller-supplied entity_npi):
    +0.000 (no identity confidence boost)

  Cap: min(score, 0.999)

  human_review_required: score < settings.human_review_threshold (default: 0.85)

Result at key milestones:
  F1                     -> 0.950
  F1 + F4                -> 0.965
  F1 + F4 + I1           -> 0.980  (>= architecture target of 0.98)
  F1 + F4 + I1 + I2      -> 0.995
  F1 + F2 + F4 + I1      -> 0.985
  no F1                  -> max 0.750, human review

The scorer is the single source of truth for confidence arithmetic. All
bundle creation and merge operations in resolver.py delegate here.
"""
from __future__ import annotations

from .config import IdentitySettings


class ConfidenceScorer:
    """
    Stateless identity confidence scorer.

    Computes identity_confidence and human_review_required for a bundle,
    given its list of contributing source IDs.

    All scoring parameters come from IdentitySettings so they can be
    tuned via environment variables without touching algorithm code.
    """

    def __init__(self, settings: IdentitySettings | None = None) -> None:
        self._s = settings or IdentitySettings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, contributing_sources: list[str] | frozenset[str]) -> float:
        """
        Compute identity_confidence from a list of contributing source IDs.

        Returns a float in [0.0, settings.max_confidence].
        Duplicate source IDs are ignored (confidence is not double-counted).
        """
        sources = frozenset(contributing_sources)

        if self._s.npi_authoritative_sources & sources:
            return self._score_with_f1(sources)

        return self._score_without_f1(sources)

    def requires_human_review(self, confidence: float) -> bool:
        """Return True if confidence is below the human-review threshold."""
        return confidence < self._s.human_review_threshold

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _score_with_f1(self, sources: frozenset[str]) -> float:
        """Score when the NPI-authoritative source (F1) is present."""
        score = self._s.f1_base_confidence

        # Each NPI-corroborating source adds a fixed boost.
        corroborating = sources & self._s.npi_corroborating_sources
        score += len(corroborating) * self._s.npi_corroborating_boost

        # F2: partial boost (NPI may be from raw or from entity_npi).
        if sources & self._s.npi_partial_sources:
            score += self._s.npi_partial_boost

        # F3/A1/A2 (npi_caller_sources): no boost applied.

        return min(score, self._s.max_confidence)

    def _score_without_f1(self, sources: frozenset[str]) -> float:
        """Score when F1 is absent -- capped at no_f1_max_confidence."""
        # Minimal incremental boost per any additional source (weak signal).
        # Corroborating/partial sources treated equally without the anchor.
        additional = len(sources)  # every source is counted, but weakly
        score = self._s.f1_base_confidence * 0.0  # start from 0
        score += additional * self._s.no_f1_per_source

        return min(score, self._s.no_f1_max_confidence)
