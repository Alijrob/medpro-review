"""
link.py -- link_and_merge_activity: UnifiedIdBundle + NormalizedRecords -> CanonicalProviderProfile (C13 wrapper).
"""
from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

from entity_linker import EntityLinker
from schema.v1.identity import UnifiedIdBundle
from schema.v1.normalized import (
    ClinicalTrialRecord,
    CmsProviderRecord,
    CourtCaseRecord,
    MedicaidEnrollmentRecord,
    MedicareEnrollmentRecord,
    NormalizedRecord,
    NpdbAggregateRecord,
    NppesRecord,
    OigLeieRecord,
    PubMedRecord,
    ReviewPlatformRecord,
    SamExclusionRecord,
    StateBoardDisciplinaryRecord,
    StateBoardLicenseRecord,
)

from ..models import LinkAndMergeInput, LinkAndMergeOutput

log = logging.getLogger(__name__)

# Discriminated deserialiser: map record_type -> proper subclass
_RECORD_TYPE_MAP: dict[str, type[NormalizedRecord]] = {
    "nppes_npi": NppesRecord,
    "oig_leie_exclusion": OigLeieRecord,
    "sam_exclusion": SamExclusionRecord,
    "cms_provider": CmsProviderRecord,
    "medicare_enrollment": MedicareEnrollmentRecord,
    "medicaid_enrollment": MedicaidEnrollmentRecord,
    "state_board_license": StateBoardLicenseRecord,
    "state_board_disciplinary": StateBoardDisciplinaryRecord,
    "court_case": CourtCaseRecord,
    "pubmed_publication": PubMedRecord,
    "clinical_trial": ClinicalTrialRecord,
    "review_summary": ReviewPlatformRecord,
    "npdb_aggregate": NpdbAggregateRecord,
}


def _deserialize_record(raw_dict: dict[str, Any]) -> NormalizedRecord | None:
    """
    Deserialise a raw dict into the proper NormalizedRecord subclass.

    Uses the 'record_type' field to pick the right class so subclass-specific
    fields (e.g., NppesRecord.organization_name) are preserved.
    Falls back to NormalizedRecord if the record_type is unknown.
    """
    record_type = raw_dict.get("record_type", "")
    cls = _RECORD_TYPE_MAP.get(record_type, NormalizedRecord)
    try:
        return cls.model_validate(raw_dict)
    except Exception as exc:  # noqa: BLE001
        activity.logger.warning(
            "link_and_merge_activity: failed to deserialise %s record: %s", record_type, exc
        )
        return None


@activity.defn(name="link_and_merge")
def link_and_merge_activity(inp: LinkAndMergeInput) -> LinkAndMergeOutput:
    """
    Build a CanonicalProviderProfile from a UnifiedIdBundle and normalised records.

    Returns LinkAndMergeOutput with the serialised profile, record type counts,
    and completeness score.
    """
    try:
        bundle = UnifiedIdBundle.model_validate(inp.bundle)
    except Exception as exc:  # noqa: BLE001
        activity.logger.error("link_and_merge_activity: invalid bundle: %s", exc)
        raise

    records: list[NormalizedRecord] = []
    for raw_dict in inp.normalized_records:
        rec = _deserialize_record(raw_dict)
        if rec is not None:
            records.append(rec)

    linker = EntityLinker()
    result = linker.build_profile(bundle, records)

    profile = result.profile
    activity.logger.info(
        "link_and_merge_activity: npi=%s completeness=%.2f is_partial=%s",
        profile.npi, profile.report_completeness_score, profile.is_partial,
    )

    counts = {k: v for k, v in result.record_type_counts.items()} if hasattr(result, "record_type_counts") else {}

    return LinkAndMergeOutput(
        profile=profile.model_dump(mode="json"),
        record_type_counts=counts,
        completeness_score=profile.report_completeness_score,
    )
