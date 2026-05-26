"""
resolve.py -- resolve_identity_activity: NormalizedRecords -> UnifiedIdBundle (C12 wrapper).
"""
from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

from identity import IdentityResolver
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

from ..models import ResolveIdentityInput, ResolveIdentityOutput

log = logging.getLogger(__name__)

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
    record_type = raw_dict.get("record_type", "")
    cls = _RECORD_TYPE_MAP.get(record_type, NormalizedRecord)
    try:
        return cls.model_validate(raw_dict)
    except Exception as exc:  # noqa: BLE001
        activity.logger.warning(
            "resolve_identity_activity: failed to deserialise %s record: %s", record_type, exc
        )
        return None


@activity.defn(name="resolve_identity")
def resolve_identity_activity(inp: ResolveIdentityInput) -> ResolveIdentityOutput:
    """
    Resolve a list of NormalizedRecord dicts into a UnifiedIdBundle for the NPI.

    Returns ResolveIdentityOutput with the bundle (or None if no records),
    confidence score, and resolution status.
    """
    if not inp.normalized_records:
        activity.logger.info(
            "resolve_identity_activity: npi=%s -- no records, skipping", inp.npi
        )
        return ResolveIdentityOutput(
            bundle=None,
            confidence=0.0,
            source_ids_contributing=[],
            resolution_status="no_records",
        )

    records: list[NormalizedRecord] = []
    for raw_dict in inp.normalized_records:
        rec = _deserialize_record(raw_dict)
        if rec is not None:
            records.append(rec)

    if not records:
        return ResolveIdentityOutput(
            bundle=None,
            confidence=0.0,
            source_ids_contributing=[],
            resolution_status="failed",
        )

    try:
        resolver = IdentityResolver()
        summary = resolver.resolve_batch(records)

        # Get the bundle for our NPI
        bundle = resolver.store.get(inp.npi)
        if bundle is None:
            return ResolveIdentityOutput(
                bundle=None,
                confidence=0.0,
                source_ids_contributing=list(summary.source_ids_seen),
                resolution_status="failed",
            )

        activity.logger.info(
            "resolve_identity_activity: npi=%s confidence=%.3f sources=%s",
            inp.npi, float(bundle.identity_confidence), list(bundle.contributing_sources),
        )

        return ResolveIdentityOutput(
            bundle=bundle.model_dump(mode="json"),
            confidence=float(bundle.identity_confidence),
            source_ids_contributing=sorted(bundle.contributing_sources),
            resolution_status="resolved",
        )

    except Exception as exc:  # noqa: BLE001
        activity.logger.error(
            "resolve_identity_activity: npi=%s unexpected error: %s", inp.npi, exc
        )
        return ResolveIdentityOutput(
            bundle=None,
            confidence=0.0,
            source_ids_contributing=[],
            resolution_status="failed",
        )
