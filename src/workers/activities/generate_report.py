"""
generate_report.py -- generate_report_activity: CanonicalProviderProfile -> ProviderReport (C17 wrapper).
"""
from __future__ import annotations

import logging

from temporalio import activity

from report import build_report, render_html
from schema.v1.profile import CanonicalProviderProfile

from ..models import GenerateReportInput, GenerateReportOutput

log = logging.getLogger(__name__)


@activity.defn(name="generate_report")
def generate_report_activity(inp: GenerateReportInput) -> GenerateReportOutput:
    """
    Build a ProviderReport from a CanonicalProviderProfile and optionally render HTML.

    Returns GenerateReportOutput with the serialised report dict, HTML string,
    and report_id.
    """
    try:
        profile = CanonicalProviderProfile.model_validate(inp.profile)
    except Exception as exc:  # noqa: BLE001
        activity.logger.error("generate_report_activity: invalid profile npi=%s: %s", inp.npi, exc)
        raise

    report = build_report(profile)

    html = ""
    if inp.include_html:
        try:
            html = render_html(report)
        except Exception as exc:  # noqa: BLE001
            activity.logger.warning(
                "generate_report_activity: HTML rendering failed npi=%s: %s", inp.npi, exc
            )
            # Don't raise -- JSON report is still valid.

    activity.logger.info(
        "generate_report_activity: npi=%s report_id=%s is_partial=%s html_len=%d",
        inp.npi, report.report_id, report.is_partial, len(html),
    )

    return GenerateReportOutput(
        report=report.model_dump(mode="json"),
        html=html,
        report_id=str(report.report_id),
    )
