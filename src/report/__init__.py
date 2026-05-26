"""
report -- C17 Report Generation Service (Phase 2-H basic).

Pure library: no network I/O. Builds ProviderReport objects from
CanonicalProviderProfile and renders them to JSON or HTML.

Public API::

    from report import build_report, render_html, ProviderReport

    report = build_report(profile)           # CanonicalProviderProfile -> ProviderReport
    json_str = report.model_dump_json()      # JSON serialisation
    html_str = render_html(report)           # Jinja2 HTML rendering

DECISIONS.md Entry 029 (Phase 2-H).
"""
from .builder import build_report
from .config import PATH_B_DISCLAIMER, ReportSettings, get_settings
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
from .renderer import render_html

__all__ = [
    # core
    "build_report",
    "render_html",
    # top-level model
    "ProviderReport",
    # section models
    "ReportProviderIdentity",
    "ReportAddress",
    "ReportLicenseEntry",
    "ReportExclusionEntry",
    "ReportDisciplinaryEntry",
    "ReportEducationEntry",
    "ReportSourceCoverage",
    # config
    "ReportSettings",
    "get_settings",
    "PATH_B_DISCLAIMER",
]
