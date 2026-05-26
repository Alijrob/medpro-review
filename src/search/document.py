"""
document.py -- Builds a ProviderDoc (OpenSearch index document) from a
CanonicalProviderProfile.

Pure function: no I/O, no side effects. Takes the profile produced by C13
(EntityLinker.build_profile) and returns a document ready to POST to
the providers-{env} index.

Field-by-field mapping rationale (see also DECISIONS.md Entry 028):

  primary_npi              <- profile.npi  (also the document _id)
  entity_type              <- profile.entity_type.value
  primary_name             <- profile.primary_name sub-fields + full_name_display
  name_variants            <- profile.name_variants full_name strings, deduplicated,
                              primary excluded, sorted for stable output
  primary_specialty        <- profile.primary_specialty (code + description)
  all_taxonomy_descriptions<- space-joined descriptions from profile.all_specialties
  known_states             <- deduplicated state codes from practice_addresses
  known_cities             <- deduplicated city names from practice_addresses
  practice_zip_codes       <- deduplicated postal_codes from practice_addresses
  gender                   <- profile.gender.value (always "unknown" until C11
                              adds basic.gender extraction -- Entry 025/027)
  identity_confidence      <- derived_signals where signal_type == "identity_confidence"
  has_active_license       <- profile.active_license_count > 0
  has_active_exclusion     <- profile.currently_excluded (set by C13 extractor)
  has_active_discipline    <- profile.has_active_discipline
  overall_risk_score       <- derived_signals where signal_type == "overall_risk_score"
                              (0.0 until C16 Analytics & Anomaly Detection, Phase 2-J)
  source_coverage_count    <- len(profile.source_coverage)
  report_count             <- 0  (not yet tracked; Phase 2-J wires the counter)
  profile_last_rebuilt_at  <- profile.updated_at.isoformat()
  last_indexed_at          <- utc_now() at call time
"""
from __future__ import annotations

from schema.v1.common import utc_now
from schema.v1.profile import CanonicalProviderProfile

from .models import ProviderDoc

# Signal type constants -- stable contract with C13 and C16
_SIG_IDENTITY_CONFIDENCE = "identity_confidence"
_SIG_OVERALL_RISK = "overall_risk_score"


def _get_signal_value(
    profile: CanonicalProviderProfile,
    signal_type: str,
    default: float = 0.0,
) -> float:
    """Extract a numeric value from derived_signals by signal_type. Returns default if absent."""
    for sig in profile.derived_signals:
        if sig.signal_type == signal_type:
            return sig.value
    return default


def build_provider_doc(profile: CanonicalProviderProfile) -> ProviderDoc:
    """
    Convert a CanonicalProviderProfile into a ProviderDoc suitable for indexing.

    All list fields are deduplicated and sorted for stable, deterministic output
    so repeated calls with the same profile produce identical documents.
    """
    name = profile.primary_name

    # Build primary_name dict -- keys mirror the OpenSearch mapping
    primary_name_dict: dict[str, str | None] = {
        "first": name.first,
        "last": name.last,
        "middle": name.middle,
        "credentials": name.credentials,
        "full_name_display": name.full_name,
    }

    # Name variants: deduplicated full_name strings, primary excluded, sorted
    primary_sort_key = name.sort_key
    variant_names: list[str] = sorted(
        {v.full_name for v in profile.name_variants if v.sort_key != primary_sort_key}
    )

    # Address facets: deduplicated, sorted for stable output
    known_states: list[str] = sorted({addr.state for addr in profile.practice_addresses})
    known_cities: list[str] = sorted({addr.city for addr in profile.practice_addresses})
    practice_zip_codes: list[str] = sorted({addr.postal_code for addr in profile.practice_addresses})

    # Specialty
    primary_specialty: dict[str, str] | None = None
    if profile.primary_specialty is not None:
        primary_specialty = {
            "code": profile.primary_specialty.code,
            "description": profile.primary_specialty.description,
        }

    all_taxonomy_descriptions = " ".join(
        t.description for t in profile.all_specialties if t.description
    )

    # Derived signals
    identity_confidence = _get_signal_value(profile, _SIG_IDENTITY_CONFIDENCE)
    overall_risk_score = _get_signal_value(profile, _SIG_OVERALL_RISK)

    return ProviderDoc(
        primary_npi=profile.npi,
        entity_type=profile.entity_type.value,
        primary_name=primary_name_dict,
        name_variants=variant_names,
        primary_specialty=primary_specialty,
        all_taxonomy_descriptions=all_taxonomy_descriptions,
        known_states=known_states,
        known_cities=known_cities,
        practice_zip_codes=practice_zip_codes,
        gender=profile.gender.value,
        identity_confidence=identity_confidence,
        has_active_license=profile.active_license_count > 0,
        has_active_exclusion=profile.currently_excluded,
        has_active_discipline=profile.has_active_discipline,
        overall_risk_score=overall_risk_score,
        source_coverage_count=len(profile.source_coverage),
        report_count=0,
        profile_last_rebuilt_at=profile.updated_at.isoformat(),
        last_indexed_at=utc_now().isoformat(),
    )
