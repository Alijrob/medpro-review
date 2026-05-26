"""
config.py -- ReportSettings for C17 Report Generation Service.

Env prefix: REPORT_
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


# Path B mandatory disclaimer (non-CRA; DECISIONS.md Entry 007)
PATH_B_DISCLAIMER = (
    "This report is provided for personal research and informational purposes only. "
    "It is NOT a consumer report as defined by the Fair Credit Reporting Act (FCRA). "
    "This report may not be used, directly or indirectly, to make decisions about "
    "employment, credit, insurance, housing, or any other FCRA-regulated purpose. "
    "All data is sourced from publicly available government registries and records. "
    "ResearchYourDoctor.com is not a Consumer Reporting Agency (CRA) and makes no "
    "representations regarding the completeness, accuracy, or currency of data provided. "
    "Data is presented as of the date shown; actual status may have changed. "
    "Consult official licensing authorities and legal counsel for authoritative information."
)


class ReportSettings(BaseSettings):
    """Settings for the report generation service."""

    # HTML rendering
    html_template_name: str = "provider_report.html.j2"

    # Partial report behaviour
    max_sources_for_full_report: int = 9  # all P1 sources

    # Compliance
    disclaimer: str = PATH_B_DISCLAIMER

    model_config = {"env_prefix": "REPORT_", "case_sensitive": False}


@lru_cache(maxsize=1)
def get_settings() -> ReportSettings:
    return ReportSettings()
