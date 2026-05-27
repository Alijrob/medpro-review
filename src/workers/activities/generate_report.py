"""
generate_report.py -- generate_report_activity: CanonicalProviderProfile -> ProviderReport (C17 wrapper).

Phase 4-H: accepts an optional ``narrative`` dict (serialised NarrativeResult) and
forwards it to render_html() so the HTML report includes the AI narrative section.
"""
from __future__ import annotations

import logging

from temporalio import activity

from ai.models import NarrativeResult
from report import build_report, render_html
from schema.v1.profile import CanonicalProviderProfile

from ..models import GenerateReportInput, GenerateReportOutput

log = logging.getLogger(__name__)


@activity.defn(name="generate_report")
def generate_report_activity(inp: GenerateReportInput) -> GenerateReportOutput:
    """
    Build a ProviderReport from a CanonicalProviderProfile and optionally render HTML.

    Phase 4-H: when inp.narrative is set, parses it as NarrativeResult and passes
    it to render_html() for inclusion in the AI narrative section.

    Returns GenerateReportOutput with the serialised report dict, HTML string,
    and report_id.
    """
    try:
        profile = CanonicalProviderProfile.model_validate(inp.profile)
    except Exception as exc:  # noqa: BLE001
        activity.logger.error("generate_report_activity: invalid profile npi=%s: %s", inp.npi, exc)
        raise

    report = build_report(profile)

    # Parse optional AI narrative (Phase 4-H)
    narrative: NarrativeResult | None = None
    if inp.narrative is not None:
        try:
            narrative = NarrativeResult.model_validate(inp.narrative)
        except Exception as exc:  # noqa: BLE001
            activity.logger.warning(
                "generate_report_activity: failed to parse narrative npi=%s: %s", inp.npi, exc
            )

    html = ""
    if inp.include_html:
        try:
            html = render_html(report, narrative=narrative)
        except Exception as exc:  # noqa: BLE001
            activity.logger.warning(
                "generate_report_activity: HTML rendering failed npi=%s: %s", inp.npi, exc
            )
            # Don't raise -- JSON report is still valid.

    activity.logger.info(
        "generate_report_activity: npi=%s report_id=%s is_partial=%s html_len=%d narrative=%s",
        inp.npi, report.report_id, report.is_partial, len(html),
        "present" if narrative else "absent",
    )

    return GenerateReportOutput(
        report=report.model_dump(mode="json"),
        html=html,
        report_id=str(report.report_id),
    )
