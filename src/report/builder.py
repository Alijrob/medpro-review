"""
builder.py -- build_report(): CanonicalProviderProfile -> ProviderReport (C17 basic).

Pure transformation. No network I/O, no state. Every field in ProviderReport is
populated from CanonicalProviderProfile fields; nothing is inferred or computed.

The disclaimer is always injected (Path B requirement; DECISIONS.md Entry 007).
"""
from __future__ import annotations

from schema.v1.profile import CanonicalProviderProfile

from .config import get_settings
from .models import (
    ProviderReport,
    ReportAddress,
    ReportDisciplinaryEntry,
    ReportEducationEntry,
    ReportExclusionEntry,
    ReportLicenseEntry,
    ReportProviderIdentity,
    ReportSourceCoverage,
)


def _display_name(profile: CanonicalProviderProfile) -> str:
    """Format a human-readable display name from the profile."""
    if profile.entity_type.value == "organization":
        return profile.organization_name or "Unknown Organization"
    n = profile.primary_name
    parts = [n.prefix, n.first, n.middle, n.last, n.suffix]
    name = " ".join(p for p in parts if p)
    if n.credentials:
        name = f"{name}, {n.credentials}"
    return name or "Unknown Provider"


def _build_identity(profile: CanonicalProviderProfile) -> ReportProviderIdentity:
    n = profile.primary_name
    credentials = []
    if n.credentials:
        credentials = [c.strip() for c in n.credentials.split(",") if c.strip()]

    primary_specialty: str | None = None
    specialty_group: str | None = None
    if profile.primary_specialty:
        primary_specialty = profile.primary_specialty.description
        # specialty_group is not stored on TaxonomyCode in v1; leave None for now

    gender_val = profile.gender.value if profile.gender else None
    gender_display: str | None = None
    if gender_val == "M":
        gender_display = "Male"
    elif gender_val == "F":
        gender_display = "Female"
    elif gender_val == "U":
        gender_display = None  # Unknown -- don't show

    return ReportProviderIdentity(
        npi=profile.npi,
        entity_type=profile.entity_type.value,
        display_name=_display_name(profile),
        first_name=n.first if profile.entity_type.value != "organization" else None,
        last_name=n.last if profile.entity_type.value != "organization" else None,
        credentials=credentials,
        primary_specialty=primary_specialty,
        specialty_group=specialty_group,
        gender=gender_display,
        sole_proprietor=None,  # not on v1 profile; available in future schema
    )


def _build_addresses(profile: CanonicalProviderProfile) -> list[ReportAddress]:
    result = []
    for i, addr in enumerate(profile.practice_addresses):
        result.append(
            ReportAddress(
                address_type="practice" if i == 0 else "additional",
                line1=addr.street_line_1,
                line2=addr.street_line_2,
                city=addr.city,
                state=addr.state,
                zip_code=addr.postal_code,
                phone=addr.phone,
                fax=getattr(addr, "fax", None),
            )
        )
    return result


def _build_licenses(profile: CanonicalProviderProfile) -> list[ReportLicenseEntry]:
    result = []
    for lic in profile.licenses:
        status_str = lic.status.value if hasattr(lic.status, "value") else str(lic.status)
        is_active = status_str.lower() in ("active", "current")
        result.append(
            ReportLicenseEntry(
                state=lic.state,
                board_name=lic.board_name,
                license_number=lic.license_number,
                license_type=lic.license_type,
                status=status_str,
                status_is_active=is_active,
                expiration_date=lic.expiration_date,
                as_of_date=lic.as_of_date,
                source_id=lic.source_id,
            )
        )
    return result


def _build_exclusions(profile: CanonicalProviderProfile) -> list[ReportExclusionEntry]:
    result = []
    for exc in profile.exclusions:
        reinstatement = getattr(exc, "reinstatement_date", None)
        is_active = reinstatement is None  # no reinstatement date = still active
        result.append(
            ReportExclusionEntry(
                authority=exc.source_registry,
                exclusion_type=exc.exclusion_type,
                effective_date=exc.exclusion_date,
                reinstatement_date=reinstatement,
                is_active=is_active,
                basis=getattr(exc, "general_notes", None),
                source_id=getattr(exc, "source_id", "unknown"),
            )
        )
    return result


def _build_disciplinary(profile: CanonicalProviderProfile) -> list[ReportDisciplinaryEntry]:
    result = []
    for action in profile.disciplinary_actions:
        result.append(
            ReportDisciplinaryEntry(
                state=action.state,
                board_name=action.board_name,
                action_type=action.action_type,
                effective_date=action.effective_date,
                is_active=action.is_active,
                basis=action.basis,
                case_number=action.case_number,
                source_id=action.source_id,
            )
        )
    return result


def _build_education(profile: CanonicalProviderProfile) -> list[ReportEducationEntry]:
    entries = []
    if profile.medical_school:
        entries.append(
            ReportEducationEntry(
                institution_name=profile.medical_school,
                degree="MD/DO/DMD",  # generic placeholder; actual degree from source
                field_of_study=None,
                graduation_year=profile.graduation_year,
            )
        )
    return entries


def _build_source_coverage(profile: CanonicalProviderProfile) -> list[ReportSourceCoverage]:
    """
    Convert CanonicalProviderProfile.source_coverage (category-level) into
    ReportSourceCoverage entries (one per source_id in sources_attempted).

    SourceCoverage aggregates per SourceCategory; we expand to per-source rows
    so the report table shows each source separately.
    """
    result = []
    succeeded_set = set(profile.sources_succeeded)
    failed_set = set(profile.sources_failed)

    for cov in profile.source_coverage:
        category_str = cov.category.value if hasattr(cov.category, "value") else str(cov.category)
        for src_id in cov.sources_attempted:
            if src_id in succeeded_set:
                status = "success"
            elif src_id in failed_set:
                status = "failed"
            else:
                status = "not_attempted"
            result.append(
                ReportSourceCoverage(
                    source_id=src_id,
                    source_category=category_str,
                    status=status,
                    fetched_at=cov.last_refreshed_at,
                )
            )
    return result


def build_report(profile: CanonicalProviderProfile) -> ProviderReport:
    """
    Transform a CanonicalProviderProfile into a ProviderReport.

    Pure function: takes a profile, returns a report. No network I/O.
    The disclaimer is always injected (Path B).
    """
    settings = get_settings()

    active_license_count = sum(
        1 for lic in profile.licenses
        if lic.status.value.lower() in ("active", "current")
    )

    return ProviderReport(
        npi=profile.npi,
        is_partial=profile.is_partial,
        report_completeness_score=profile.report_completeness_score,
        overall_confidence=float(profile.overall_confidence),
        last_full_refresh_at=profile.last_full_refresh_at,
        # -- identity --
        identity=_build_identity(profile),
        addresses=_build_addresses(profile),
        # -- licenses --
        licenses=_build_licenses(profile),
        has_active_license=profile.active_license_count > 0,
        active_license_count=active_license_count,
        # -- exclusions --
        exclusions=_build_exclusions(profile),
        has_active_exclusion=profile.currently_excluded,
        # -- disciplinary --
        disciplinary_actions=_build_disciplinary(profile),
        has_active_discipline=profile.has_active_discipline,
        # -- education --
        education=_build_education(profile),
        # -- insurance --
        accepts_medicare=profile.accepts_medicare,
        opted_out_of_medicare=profile.opted_out_of_medicare,
        accepts_medicaid=profile.accepts_medicaid,
        # -- source coverage --
        sources_attempted=list(profile.sources_attempted),
        sources_succeeded=list(profile.sources_succeeded),
        sources_failed=list(profile.sources_failed),
        source_coverage=_build_source_coverage(profile),
        # -- compliance --
        disclaimer=settings.disclaimer,
        report_disclaimer_required=profile.report_disclaimer_required,
        has_pending_corrections=profile.has_pending_corrections,
    )
