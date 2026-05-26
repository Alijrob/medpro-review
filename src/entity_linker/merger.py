"""
merger.py -- EntityLinker: builds CanonicalProviderProfile from resolved data (C13).

Phase 2-F: Entity Linking & Merge MVP.

The EntityLinker is the central component of C13. Given a UnifiedIdBundle
(C12 output) and all contributing NormalizedRecords for that NPI, it:

  1. Routes each record to its per-type extractor function.
  2. Assembles all CanonicalProviderProfile sub-models.
  3. Calls get_specialty_group() from the F1 normalizer (I4 crosswalk).
  4. Computes all four derived signals via signals.py.
  5. Calculates the data_completeness score and sets is_partial.
  6. Returns a MergeResult wrapping the finished profile.

Library pattern (same as src/normalizers/, src/identity/):
  - No network I/O, no DB writes, no side effects.
  - Stateless: create one EntityLinker instance and reuse it.
  - Will become a Temporal activity in Phase 2-H.
"""
from __future__ import annotations

from schema.v1.common import SourceCategory, utc_now
from schema.v1.identity import UnifiedIdBundle
from schema.v1.normalized import (
    ClinicalTrialRecord,
    CmsProviderRecord,
    MedicaidEnrollmentRecord,
    MedicareEnrollmentRecord,
    NormalizedRecord,
    NppesRecord,
    OigLeieRecord,
    PubMedRecord,
    SamExclusionRecord,
)
from schema.v1.profile import (
    CanonicalProviderProfile,
    ExclusionRecord,
    SourceCoverage,
)

from .config import LinkerSettings
from .extractors import (
    extract_cms_practice_context,
    extract_hospital_affiliations,
    extract_medicaid_participation,
    extract_medicare_participation,
    extract_oig_exclusions,
    extract_publications,
    extract_sam_exclusions,
)
from .models import MergeResult, RecordTypeCounts
from .signals import COMPLETENESS_WEIGHTS, compute_derived_signals


# ---------------------------------------------------------------------------
# Record-type router
# ---------------------------------------------------------------------------

# Map record_type discriminator -> NormalizedRecord subclass bucket key.
# Adding a new record type in Phase 3 requires one line here.
_BUCKET_MAP: dict[str, str] = {
    "nppes_npi":             "nppes",
    "oig_leie_exclusion":    "oig",
    "sam_exclusion":         "sam",
    "cms_provider":          "cms",
    "medicare_enrollment":   "medicare",
    "medicaid_enrollment":   "medicaid",
    "pubmed_publication":    "pubmed",
    "clinical_trial":        "trials",
}

# Source-ID to SourceCategory mapping (P1 sources only for MVP).
_SOURCE_CATEGORY: dict[str, SourceCategory] = {
    "F1": SourceCategory.FEDERAL,
    "F2": SourceCategory.FEDERAL,
    "F3": SourceCategory.FEDERAL,
    "F4": SourceCategory.FEDERAL,
    "I1": SourceCategory.FEDERAL,
    "I2": SourceCategory.FEDERAL,
    "A1": SourceCategory.ACADEMIC,
    "A2": SourceCategory.ACADEMIC,
}


def _group_records(
    records: list[NormalizedRecord],
) -> tuple[dict[str, list], int]:
    """
    Group records by bucket key (derived from record_type discriminator).

    Returns (grouped_dict, unrecognized_count).
    Unrecognized record_types are silently counted but not stored; Phase 3
    adapters will add their type mappings to _BUCKET_MAP before use.
    """
    grouped: dict[str, list] = {
        "nppes": [], "oig": [], "sam": [], "cms": [],
        "medicare": [], "medicaid": [], "pubmed": [], "trials": [],
    }
    unrecognized = 0
    for rec in records:
        bucket = _BUCKET_MAP.get(rec.record_type)
        if bucket is not None:
            grouped[bucket].append(rec)
        else:
            unrecognized += 1
    return grouped, unrecognized


def _build_source_coverage(
    contributing_sources: list[str],
) -> list[SourceCoverage]:
    """
    Build SourceCoverage entries grouped by SourceCategory.

    MVP: sources_attempted == sources_succeeded (the pipeline feeds only
    successfully-normalized records to the linker; failed fetches stay in
    SourceHealthRecord, not here). Phase 2-H Temporal workflow will track
    attempted vs succeeded at the workflow level.
    """
    # Group source IDs by category
    by_category: dict[SourceCategory, list[str]] = {}
    for src in contributing_sources:
        cat = _SOURCE_CATEGORY.get(src, SourceCategory.FEDERAL)
        by_category.setdefault(cat, []).append(src)

    # Denominator per category (P1 sources only)
    _CATEGORY_TOTAL: dict[SourceCategory, int] = {
        SourceCategory.FEDERAL: 6,   # F1, F2, F3, F4, I1, I2
        SourceCategory.ACADEMIC: 2,  # A1, A2
    }

    coverage: list[SourceCoverage] = []
    for cat, srcs in sorted(by_category.items(), key=lambda x: x[0].value):
        total = _CATEGORY_TOTAL.get(cat, max(len(srcs), 1))
        conf = round(min(len(srcs) / total, 1.0), 4)
        coverage.append(
            SourceCoverage(
                category=cat,
                sources_attempted=sorted(srcs),
                sources_succeeded=sorted(srcs),
                last_refreshed_at=utc_now(),
                coverage_confidence=conf,
            )
        )
    return coverage


def _compute_completeness_score(
    contributing_sources: list[str],
    known_address_count: int,
) -> float:
    """
    Compute the report_completeness_score using COMPLETENESS_WEIGHTS.

    Mirrors the logic in signals.compute_data_completeness so that the
    profile field and the derived signal always agree.
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
        w for sec, w in COMPLETENESS_WEIGHTS.items()
        if section_present.get(sec, False)
    )
    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# EntityLinker
# ---------------------------------------------------------------------------


class EntityLinker:
    """
    Builds a CanonicalProviderProfile from a UnifiedIdBundle and its records.

    Usage::

        linker = EntityLinker()
        result = linker.build_profile(bundle, records)
        profile = result.profile
    """

    def __init__(self, settings: LinkerSettings | None = None) -> None:
        self._settings = settings or LinkerSettings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_profile(
        self,
        bundle: UnifiedIdBundle,
        records: list[NormalizedRecord],
    ) -> MergeResult:
        """
        Assemble a CanonicalProviderProfile from resolved identity + source data.

        Args:
            bundle:  The UnifiedIdBundle produced by C12 (IdentityResolver).
            records: All NormalizedRecord objects for bundle.primary_npi.
                     May be empty if only F1 identity data is available.

        Returns:
            MergeResult with the finished CanonicalProviderProfile and metadata.
        """
        # 1. Route records into buckets by record_type discriminator
        grouped, unrecognized_count = _group_records(records)

        # 2. Per-type extraction
        exclusions: list[ExclusionRecord] = (
            extract_oig_exclusions(grouped["oig"])
            + extract_sam_exclusions(grouped["sam"])
        )
        currently_excluded = any(e.is_active for e in exclusions)

        hospital_affiliations = extract_hospital_affiliations(grouped["cms"])

        cms_context = extract_cms_practice_context(grouped["cms"])

        medicare_participations, accepts_medicare, opted_out_medicare = (
            extract_medicare_participation(grouped["medicare"])
        )

        # CMS Care Compare (F4) may also carry opted_out flag -- combine.
        if cms_context["opted_out_from_f4"] and not opted_out_medicare:
            opted_out_medicare = True
        # F4 accepts_medicare is secondary to I1 (which is the enrollment record).
        if accepts_medicare is None:
            accepts_medicare = cms_context["accepts_medicare_from_f4"]

        medicaid_participations, accepts_medicaid = (
            extract_medicaid_participation(grouped["medicaid"])
        )

        insurance_participation = medicare_participations + medicaid_participations

        recent_publications, publication_count = extract_publications(
            grouped["pubmed"],
            self._settings.max_recent_publications,
        )
        clinical_trial_count = len(grouped["trials"])

        # 3. Specialty group via I4 taxonomy crosswalk
        specialty_group: str | None = None
        if grouped["nppes"]:
            try:
                from normalizers.sources import get_specialty_group
                specialty_group = get_specialty_group(grouped["nppes"][0])
            except Exception:  # noqa: BLE001 -- import/crosswalk errors are non-fatal
                pass

        # 4. Source tracking
        contributing = list(bundle.contributing_sources)
        sources_succeeded = contributing
        sources_attempted = contributing  # MVP: attempted == succeeded
        source_coverage = _build_source_coverage(contributing)

        # 5. Completeness
        address_count = len(bundle.known_addresses)
        completeness_score = _compute_completeness_score(contributing, address_count)
        is_partial = (
            completeness_score < self._settings.completeness_threshold_for_partial
            or bundle.human_review_required
        )

        # 6. Derived signals
        derived_signals = compute_derived_signals(
            exclusions=exclusions,
            bundle=bundle,
            specialty_group=specialty_group,
            known_address_count=address_count,
        )

        # 7. Organization name (from F1 if entity_type=ORGANIZATION)
        organization_name: str | None = None
        if grouped["nppes"]:
            f1: NppesRecord = grouped["nppes"][0]
            if f1.organization_name:
                organization_name = f1.organization_name.strip() or None

        # 8. Assemble CanonicalProviderProfile
        now = utc_now()
        profile = CanonicalProviderProfile(
            npi=bundle.primary_npi,
            bundle_id=bundle.bundle_id,
            entity_type=bundle.entity_type,
            primary_name=bundle.primary_name,
            name_variants=list(bundle.name_variants),
            gender=bundle.gender,
            primary_specialty=bundle.primary_specialty,
            all_specialties=list(bundle.all_taxonomies),
            practice_addresses=list(bundle.known_addresses),
            organization_name=organization_name,
            graduation_year=cms_context["graduation_year"],
            medical_school=cms_context["medical_school"],
            exclusions=exclusions,
            currently_excluded=currently_excluded,
            hospital_affiliations=hospital_affiliations,
            group_practice_name=cms_context["group_practice_name"],
            group_practice_pac_id=cms_context["group_practice_pac_id"],
            insurance_participation=insurance_participation,
            accepts_medicare=accepts_medicare,
            opted_out_of_medicare=opted_out_medicare,
            accepts_medicaid=accepts_medicaid,
            publication_count=publication_count,
            recent_publications=recent_publications,
            clinical_trial_count=clinical_trial_count,
            derived_signals=derived_signals,
            overall_confidence=round(bundle.identity_confidence, 4),
            report_completeness_score=completeness_score,
            is_partial=is_partial,
            source_coverage=source_coverage,
            sources_attempted=sorted(sources_attempted),
            sources_succeeded=sorted(sources_succeeded),
            sources_failed=[],
            created_at=now,
            updated_at=now,
            # Path B compliance -- always True on non-CRA path
            report_disclaimer_required=True,
        )

        # 9. Build and return MergeResult
        counts = RecordTypeCounts(
            nppes=len(grouped["nppes"]),
            oig_leie=len(grouped["oig"]),
            sam_gov=len(grouped["sam"]),
            cms_care_compare=len(grouped["cms"]),
            medicare_enrollment=len(grouped["medicare"]),
            medicaid_enrollment=len(grouped["medicaid"]),
            pubmed=len(grouped["pubmed"]),
            clinical_trials=len(grouped["trials"]),
            unrecognized=unrecognized_count,
        )

        return MergeResult(
            profile=profile,
            record_counts=counts,
            merged_at=now,
            specialty_group=specialty_group,
        )
