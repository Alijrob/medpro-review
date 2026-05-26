"""
models.py -- Output types for the EntityLinker (C13, Phase 2-F).

MergeResult wraps a CanonicalProviderProfile with per-call metadata useful
for logging, auditing, and downstream pipeline orchestration. The profile
itself is the primary artifact; the metadata travels with it through the
Temporal workflow (Phase 2-H) without being stored in the profile schema.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from schema.v1.common import MedproBaseModel, utc_now
from schema.v1.profile import CanonicalProviderProfile


class RecordTypeCounts(MedproBaseModel):
    """Per-record-type input counts for a single merge call."""

    nppes: int = 0
    oig_leie: int = 0
    sam_gov: int = 0
    cms_care_compare: int = 0
    medicare_enrollment: int = 0
    medicaid_enrollment: int = 0
    pubmed: int = 0
    clinical_trials: int = 0
    unrecognized: int = 0

    @property
    def total(self) -> int:
        return (
            self.nppes + self.oig_leie + self.sam_gov + self.cms_care_compare
            + self.medicare_enrollment + self.medicaid_enrollment
            + self.pubmed + self.clinical_trials + self.unrecognized
        )


class MergeResult(MedproBaseModel):
    """
    Output of EntityLinker.build_profile().

    Carries the built CanonicalProviderProfile plus metadata about the merge
    call: how many records of each type were consumed, and when the merge ran.
    """

    profile: CanonicalProviderProfile = Field(
        ...,
        description="The assembled CanonicalProviderProfile for this provider.",
    )
    record_counts: RecordTypeCounts = Field(
        default_factory=RecordTypeCounts,
        description="Number of NormalizedRecords consumed per source type.",
    )
    merged_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp when build_profile() completed.",
    )
    specialty_group: str | None = Field(
        default=None,
        description=(
            "Specialty group string resolved from the I4 taxonomy crosswalk "
            "(e.g., 'Family Medicine'). None when the taxonomy code is absent "
            "or not found in the crosswalk."
        ),
    )
