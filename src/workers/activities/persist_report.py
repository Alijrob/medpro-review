"""
persist_report.py -- persist_report_activity: persists ProviderPipelineResult to Aurora (C18).

Phase 2-I activity.  Best-effort: returns PersistReportOutput(persisted=False)
if the database is not configured or unavailable -- never raises.

Called as the final step of ProviderPipelineWorkflow when inp.report_id is set.
"""
from __future__ import annotations

import logging
from uuid import UUID

from temporalio import activity

from workers.models import PersistReportInput, PersistReportOutput, ProviderPipelineResult

log = logging.getLogger(__name__)


@activity.defn(name="persist_report")
def persist_report_activity(inp: PersistReportInput) -> PersistReportOutput:
    """
    Persist a completed ProviderPipelineResult to the reports table.

    Steps:
        1. Check that REPORT_DATABASE_URL (or DATABASE_URL) is set.
        2. Deserialise inp.pipeline_result -> ProviderPipelineResult.
        3. Call ReportRepository.mark_complete() or mark_failed() based on pipeline_status.

    Never raises -- all errors returned in PersistReportOutput.error_message.
    """
    # Deferred import: avoids pulling psycopg2 at import time when DB is absent.
    from backend.report_service.config import get_settings  # noqa: PLC0415
    from backend.report_service.repository import ReportRepository  # noqa: PLC0415

    settings = get_settings()
    if not settings.is_db_configured:
        return PersistReportOutput(
            persisted=False,
            error_message="Report database not configured (REPORT_DATABASE_URL or DATABASE_URL not set).",
        )

    # Validate report_id
    if not inp.report_id:
        return PersistReportOutput(
            persisted=False,
            error_message="persist_report_activity: report_id is empty.",
        )

    try:
        report_id = UUID(inp.report_id)
    except ValueError as exc:
        return PersistReportOutput(
            persisted=False,
            error_message=f"persist_report_activity: invalid report_id UUID: {exc}",
        )

    # Deserialise pipeline result
    try:
        result = ProviderPipelineResult.model_validate(inp.pipeline_result)
    except Exception as exc:  # noqa: BLE001
        return PersistReportOutput(
            persisted=False,
            error_message=f"persist_report_activity: invalid pipeline_result: {exc}",
        )

    try:
        repo = ReportRepository(settings.database_url)

        if result.pipeline_status in ("complete", "partial") and result.report is not None:
            repo.mark_complete(
                report_id=report_id,
                report_json=result.report,
                report_html=result.html or "",
                sources_attempted=result.sources_attempted,
                sources_succeeded=result.sources_succeeded,
                sources_failed=result.sources_failed,
                is_partial=result.is_partial,
                html_max_bytes=settings.html_max_storage_bytes,
            )
        else:
            # no_data or failed status
            repo.mark_failed(
                report_id=report_id,
                error_message=result.error_message or f"Pipeline status: {result.pipeline_status}",
            )

        log.info(
            "persist_report_activity: persisted report_id=%s pipeline_status=%s",
            inp.report_id,
            result.pipeline_status,
        )
        return PersistReportOutput(persisted=True)

    except Exception as exc:  # noqa: BLE001
        log.warning(
            "persist_report_activity: DB write failed for report_id=%s: %s",
            inp.report_id,
            exc,
        )
        return PersistReportOutput(
            persisted=False,
            error_message=f"persist_report_activity: DB write failed: {exc}",
        )
