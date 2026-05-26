"""
signals.py -- Derived signal computation for C13 (Phase 2-F).

Each function computes one DerivedSignalSummary from profile state and
contributing source data. Signals are stateless and independently testable.

Signal types produced here:
  exclusion_flag        -- 1.0 if currently excluded; 0.0 otherwise
  identity_confidence   -- mirrors UnifiedIdBundle.identity_confidence
  specialty_classification -- 1.0 if specialty group resolved; 0.0 if unknown
  data_completeness     -- fraction of expected data sections populated

The signal_type strings are a stable contract: downstream report generation
(C17, Phase 2-I) keys on them for rendering.
"""
from __future__ import annotations

from schema.v1.common import utc_now
from schema.v1.identity import UnifiedIdBundle
from schema.v1.profile import DerivedSignalSummary, ExclusionRecord

# ---------------------------------------------------------------------------
# Completeness weight table
# Each key is a logical section; value is its weight (weights sum to 1.0).
# ---------------------------------------------------------------------------

COMPLETENESS_WEIGHTS: dict[str, float] = {
    "identity_anchor":        0.30,  # F1 in contributing_sources
    "exclusion_checked":      0.20,  # F2 or F3 in contributing_sources
    "medicare_status":        0.15,  # I1 in contributing_sources
    "address_present":        0.10,  # >= 1 known address in bundle
    "hospital_affiliation":   0.10,  # F4 in contributing_sources
    "medicaid_status":        0.08,  # I2 in contributing_sources
    "publications_checked":   0.04,  # A1 in contributing_sources
    "clinical_trials_checked":0.03,  # A2 in contributing_sources
}

assert abs(sum(COMPLETENESS_WEIGHTS.values()) - 1.0) < 1e-9, (
    "COMPLETENESS_WEIGHTS must sum to 1.0"
)


# ---------------------------------------------------------------------------
# Signal builders
# ---------------------------------------------------------------------------


def compute_exclusion_flag(
    exclusions: list[ExclusionRecord],
    contributing_sources: list[str],
) -> DerivedSignalSummary:
    """
    Exclusion flag signal (signal_type="exclusion_flag").

    value=1.0 if any exclusion is currently active.
    value=0.0 if sources were checked and no active exclusion exists.

    The distinction between "checked but no exclusion" and "not checked" is
    captured by whether F2/F3 appear in contributing_sources. Callers should
    not render an "all clear" badge when neither F2 nor F3 was checked.
    """
    is_excluded = any(e.is_active for e in exclusions)
    exclusion_sources = [s for s in contributing_sources if s in ("F2", "F3")]
    checked = bool(exclusion_sources)

    if is_excluded:
        explanation = (
            "ALERT: Provider has an active federal exclusion record "
            f"({', '.join(sorted(set(e.source_registry for e in exclusions if e.is_active)))}). "
            "Excluded providers may not bill federal healthcare programs."
        )
        value = 1.0
    elif checked:
        explanation = (
            "No active federal exclusions found in "
            f"{', '.join(exclusion_sources)} as of last refresh."
        )
        value = 0.0
    else:
        explanation = (
            "Federal exclusion sources (OIG LEIE, SAM.gov) were not checked "
            "in this data cycle. Exclusion status is unknown."
        )
        value = 0.0

    return DerivedSignalSummary(
        signal_type="exclusion_flag",
        value=value,
        confidence=0.95 if checked else 0.0,
        explanation=explanation,
        contributing_sources=exclusion_sources,
        computed_at=utc_now(),
    )


def compute_identity_confidence(bundle: UnifiedIdBundle) -> DerivedSignalSummary:
    """
    Identity confidence signal (signal_type="identity_confidence").

    Mirrors the UnifiedIdBundle.identity_confidence value. Provides a
    standardized DerivedSignalSummary surface for the report renderer and
    for the DerivedSignals Aurora table (migration 0001).
    """
    confidence = bundle.identity_confidence
    sources = list(bundle.contributing_sources)
    n = len(sources)

    if confidence >= 0.98:
        quality = "high"
    elif confidence >= 0.85:
        quality = "moderate"
    else:
        quality = "low (human review required)"

    return DerivedSignalSummary(
        signal_type="identity_confidence",
        value=round(confidence, 4),
        confidence=round(confidence, 4),
        explanation=(
            f"Identity confidence {confidence:.3f} ({quality}). "
            f"Based on {n} contributing source{'s' if n != 1 else ''}: "
            f"{', '.join(sources) if sources else 'none'}."
        ),
        contributing_sources=sources,
        computed_at=utc_now(),
    )


def compute_specialty_classification(
    specialty_group: str | None,
    contributing_sources: list[str],
) -> DerivedSignalSummary:
    """
    Specialty classification signal (signal_type="specialty_classification").

    value=1.0 when a specialty group was resolved from the I4 taxonomy
    crosswalk; 0.0 when the taxonomy code was absent or unknown.

    The specialty_group string (e.g., "Family Medicine") is embedded in
    the explanation for the report renderer.
    """
    f1_present = "F1" in contributing_sources

    if specialty_group:
        return DerivedSignalSummary(
            signal_type="specialty_classification",
            value=1.0,
            confidence=0.95 if f1_present else 0.5,
            explanation=f"Provider specialty group: {specialty_group}.",
            contributing_sources=["F1"] if f1_present else [],
            computed_at=utc_now(),
        )
    else:
        return DerivedSignalSummary(
            signal_type="specialty_classification",
            value=0.0,
            confidence=0.0,
            explanation=(
                "Specialty group could not be determined from available "
                "taxonomy codes. Provider may be an organization or have "
                "an uncommon specialty code."
            ),
            contributing_sources=["F1"] if f1_present else [],
            computed_at=utc_now(),
        )


def compute_data_completeness(
    contributing_sources: list[str],
    known_address_count: int,
) -> DerivedSignalSummary:
    """
    Data completeness signal (signal_type="data_completeness").

    value is the weighted fraction of expected data sections that are
    populated (0.0-1.0). Uses COMPLETENESS_WEIGHTS as the rubric.
    """
    src_set = set(contributing_sources)

    section_present: dict[str, bool] = {
        "identity_anchor":         "F1" in src_set,
        "exclusion_checked":       bool(src_set & {"F2", "F3"}),
        "medicare_status":         "I1" in src_set,
        "address_present":         known_address_count > 0,
        "hospital_affiliation":    "F4" in src_set,
        "medicaid_status":         "I2" in src_set,
        "publications_checked":    "A1" in src_set,
        "clinical_trials_checked": "A2" in src_set,
    }

    score = sum(
        weight
        for section, weight in COMPLETENESS_WEIGHTS.items()
        if section_present.get(section, False)
    )
    score = round(min(score, 1.0), 4)

    missing = [s for s, present in section_present.items() if not present]
    if missing:
        missing_str = ", ".join(missing)
        detail = f"Sections not yet populated: {missing_str}."
    else:
        detail = "All expected data sections are populated."

    return DerivedSignalSummary(
        signal_type="data_completeness",
        value=score,
        confidence=score,
        explanation=f"Data completeness score: {score:.2f}. {detail}",
        contributing_sources=sorted(src_set),
        computed_at=utc_now(),
    )


# ---------------------------------------------------------------------------
# Composite builder
# ---------------------------------------------------------------------------


def compute_derived_signals(
    *,
    exclusions: list[ExclusionRecord],
    bundle: UnifiedIdBundle,
    specialty_group: str | None,
    known_address_count: int,
) -> list[DerivedSignalSummary]:
    """
    Compute all four MVP derived signals and return them as an ordered list.

    Order: exclusion_flag, identity_confidence, specialty_classification,
    data_completeness. This ordering is stable across calls and matches the
    expected rendering order in the report template.
    """
    sources = list(bundle.contributing_sources)
    return [
        compute_exclusion_flag(exclusions, sources),
        compute_identity_confidence(bundle),
        compute_specialty_classification(specialty_group, sources),
        compute_data_completeness(sources, known_address_count),
    ]
