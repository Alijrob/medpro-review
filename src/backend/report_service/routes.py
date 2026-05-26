"""
routes.py -- Report Service API routes (Phase 2-I).

Endpoints:

    GET  /healthz                           -- liveness
    GET  /readyz                            -- readiness

    POST /v1/reports/from-profile           -- synchronous: build from profile (Phase 2-H, kept)
    POST /v1/reports/from-profile/html      -- synchronous: HTML from profile (Phase 2-H, kept)

    POST /v1/reports/request                -- async: request NPI report via Temporal pipeline
    GET  /v1/reports/{report_id}            -- poll status + retrieve report when complete

Phase 2-I new endpoints:
    POST /v1/reports/request
        Validates NPI, generates a report_id UUID, creates a DB row (if DB configured),
        fires ProviderPipelineWorkflow (if Temporal configured), returns immediately.
        Always returns 200 with {report_id, status, db_persisted, temporal_queued}.

    GET  /v1/reports/{report_id}
        Returns the current status row from the reports table.
        Returns 503 if DB not configured, 422 for invalid UUID, 404 if not found.

Singleton injection:
    _set_repo(repo)             -- injected by app.py startup event
    _set_temporal_client(c)     -- injected by app.py startup event
    Both default to None (test-safe).
"""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ValidationError

from report import build_report, render_html
from schema.v1.profile import CanonicalProviderProfile
from workers.models import ProviderPipelineInput

router = APIRouter()

# ---------------------------------------------------------------------------
# Singleton references (set by app factory; None = not configured)
# ---------------------------------------------------------------------------

_repo = None           # ReportRepository | None
_temporal_client = None  # temporalio.client.Client | None


def _set_repo(repo: Any) -> None:  # typed as Any to avoid importing at module level
    global _repo
    _repo = repo


def _set_temporal_client(client: Any) -> None:
    global _temporal_client
    _temporal_client = client


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


@router.get("/healthz", tags=["health"])
def healthz() -> dict:
    return {"status": "ok", "service": "report-service"}


@router.get("/readyz", tags=["health"])
def readyz() -> dict:
    return {"status": "ok", "service": "report-service"}


# ---------------------------------------------------------------------------
# Phase 2-H synchronous endpoints (kept for direct-profile testing)
# ---------------------------------------------------------------------------


class BuildReportRequest(BaseModel):
    """Request body for POST /v1/reports/from-profile."""
    profile: dict  # serialised CanonicalProviderProfile


class ReportResponse(BaseModel):
    """JSON report response envelope."""
    report_id: str
    npi: str
    is_partial: bool
    report: dict


@router.post(
    "/v1/reports/from-profile",
    response_model=ReportResponse,
    status_code=200,
    tags=["reports"],
    summary="Build a report synchronously from a CanonicalProviderProfile",
    description=(
        "Phase 2-H: accepts a serialised CanonicalProviderProfile and returns a ProviderReport. "
        "Synchronous, no persistence, no Temporal."
    ),
)
def build_report_from_profile(request: BuildReportRequest) -> ReportResponse:
    try:
        profile = CanonicalProviderProfile.model_validate(request.profile)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid CanonicalProviderProfile: {exc.error_count()} validation error(s)",
        ) from exc

    report = build_report(profile)
    return ReportResponse(
        report_id=str(report.report_id),
        npi=report.npi,
        is_partial=report.is_partial,
        report=report.model_dump(mode="json"),
    )


@router.post(
    "/v1/reports/from-profile/html",
    response_class=Response,
    status_code=200,
    tags=["reports"],
    summary="Build an HTML report synchronously from a CanonicalProviderProfile",
    description="Phase 2-H: returns rendered HTML. Synchronous, no persistence.",
)
def build_html_report_from_profile(request: BuildReportRequest) -> Response:
    try:
        profile = CanonicalProviderProfile.model_validate(request.profile)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid CanonicalProviderProfile: {exc.error_count()} validation error(s)",
        ) from exc

    report = build_report(profile)
    try:
        html = render_html(report)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"HTML rendering failed: {exc}") from exc

    return Response(content=html, media_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# Phase 2-I: async report request + status polling
# ---------------------------------------------------------------------------

_NPI_RE = re.compile(r"^\d{10}$")


class ReportRequestBody(BaseModel):
    """Request body for POST /v1/reports/request."""
    npi: str


class ReportRequestResponse(BaseModel):
    """Response envelope for POST /v1/reports/request."""
    report_id: str
    status: str  # always "queued"
    npi: str
    db_persisted: bool  # True if a reports-table row was created
    temporal_queued: bool  # True if ProviderPipelineWorkflow was fired
    message: str | None = None  # diagnostic notes when something is unconfigured


class ReportStatusResponse(BaseModel):
    """Response envelope for GET /v1/reports/{report_id}."""
    report_id: str
    npi: str
    status: str
    is_partial: bool
    payment_status: str = "unpaid"  # unpaid | pending | paid | refunded
    requested_at: str | None
    started_at: str | None
    completed_at: str | None
    expires_at: str | None
    temporal_workflow_id: str | None
    sources_attempted: list[str]
    sources_succeeded: list[str]
    sources_failed: list[str]
    report: dict | None  # populated when status == complete/partial
    has_html: bool


@router.post(
    "/v1/reports/request",
    response_model=ReportRequestResponse,
    status_code=200,
    tags=["reports"],
    summary="Request an NPI provider report (async via Temporal pipeline)",
    description=(
        "Phase 2-I: validates NPI, creates a reports-table row (if DB configured), "
        "fires ProviderPipelineWorkflow (if Temporal configured), returns {report_id} "
        "immediately.  Poll GET /v1/reports/{report_id} for status + result."
    ),
)
async def request_report(body: ReportRequestBody) -> ReportRequestResponse:
    npi = body.npi.strip()
    if not _NPI_RE.match(npi):
        raise HTTPException(
            status_code=422,
            detail="NPI must be exactly 10 digits (numeric).",
        )

    report_id: str = str(uuid4())  # fallback UUID if DB not configured
    db_persisted = False
    temporal_queued = False
    messages: list[str] = []

    # --- DB row creation ---
    if _repo is not None:
        try:
            from uuid import UUID as _UUID  # noqa: PLC0415
            db_id = _repo.create_row(npi=npi)
            report_id = str(db_id)
            db_persisted = True
        except Exception as exc:  # noqa: BLE001
            messages.append(f"DB unavailable: {type(exc).__name__}")
    else:
        messages.append("Report DB not configured (REPORT_DATABASE_URL not set).")

    # --- Temporal workflow ---
    if _temporal_client is not None:
        try:
            from workers.config import get_settings as _get_worker_settings  # noqa: PLC0415
            wf_id = f"report-{npi}-{report_id}"
            await _temporal_client.start_workflow(
                "ProviderPipeline",
                ProviderPipelineInput(npi=npi, report_id=report_id),
                id=wf_id,
                task_queue=_get_worker_settings().temporal_task_queue,
            )
            temporal_queued = True
            # Update workflow ID in DB
            if _repo is not None and db_persisted:
                try:
                    from uuid import UUID as _UUID2  # noqa: PLC0415
                    _repo.set_workflow_id(_UUID2(report_id), wf_id)
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            messages.append(f"Temporal unavailable: {type(exc).__name__}")
    else:
        messages.append("Temporal not configured (REPORT_TEMPORAL_ADDRESS not set).")

    return ReportRequestResponse(
        report_id=report_id,
        status="queued",
        npi=npi,
        db_persisted=db_persisted,
        temporal_queued=temporal_queued,
        message="; ".join(messages) if messages else None,
    )


@router.get(
    "/v1/reports/{report_id}",
    response_model=ReportStatusResponse,
    tags=["reports"],
    summary="Poll report status and retrieve result",
    description=(
        "Phase 2-I: returns the current status of a report request. "
        "Returns 503 when DB is not configured; 404 when report_id is not found."
    ),
)
def get_report_status(report_id: str) -> ReportStatusResponse:
    if _repo is None:
        raise HTTPException(
            status_code=503,
            detail="Report persistence not configured (REPORT_DATABASE_URL not set).",
        )

    # Validate UUID format
    try:
        from uuid import UUID  # noqa: PLC0415
        uuid_obj = UUID(report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid report_id: must be a UUID. Got: {report_id!r}",
        ) from exc

    row = _repo.get_row(uuid_obj)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id!r} not found.",
        )

    return ReportStatusResponse(
        report_id=row["report_id"],
        npi=row["npi"],
        status=row["status"],
        is_partial=row["is_partial"],
        payment_status=row.get("payment_status", "unpaid"),
        requested_at=row.get("requested_at"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        expires_at=row.get("expires_at"),
        temporal_workflow_id=row.get("temporal_workflow_id"),
        sources_attempted=row.get("sources_attempted", []),
        sources_succeeded=row.get("sources_succeeded", []),
        sources_failed=row.get("sources_failed", []),
        report=row.get("report"),
        has_html=row.get("has_html", False),
    )


# ---------------------------------------------------------------------------
# Phase 2-N: GET /v1/reports/{report_id}/pdf
# ---------------------------------------------------------------------------


@router.get(
    "/v1/reports/{report_id}/pdf",
    response_class=Response,
    status_code=200,
    tags=["reports"],
    summary="Download a completed, paid provider report as a PDF",
    description=(
        "Phase 2-N: renders the stored report_html to a PDF using WeasyPrint. "
        "Requires status=complete|partial AND payment_status=paid. "
        "Returns application/pdf bytes with Content-Disposition: attachment."
    ),
)
def get_report_pdf(report_id: str) -> Response:
    # -- Validate UUID first (cheap, no DB required) --
    try:
        from uuid import UUID  # noqa: PLC0415
        uuid_obj = UUID(report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid report_id: must be a UUID. Got: {report_id!r}",
        ) from exc

    # -- DB required --
    if _repo is None:
        raise HTTPException(
            status_code=503,
            detail="Report persistence not configured (REPORT_DATABASE_URL not set).",
        )

    # -- Fetch row --
    row = _repo.get_row(uuid_obj)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id!r} not found.",
        )

    # -- Payment gate --
    payment_status = row.get("payment_status", "unpaid")
    if payment_status != "paid":
        raise HTTPException(
            status_code=402,
            detail=(
                f"PDF download requires a completed payment "
                f"(payment_status={payment_status!r}). "
                "Complete payment via POST /v1/payments/checkout."
            ),
        )

    # -- Report-complete gate --
    status = row.get("status", "queued")
    if status not in ("complete", "partial"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Report is not yet complete (status={status!r}). "
                "Poll GET /v1/reports/{report_id} until status is "
                "'complete' or 'partial'."
            ),
        )

    # -- HTML must be present --
    html = row.get("report_html") or ""
    if not html:
        raise HTTPException(
            status_code=422,
            detail=(
                "Report HTML is not available for this report "
                "(may have been truncated at storage time due to size limits)."
            ),
        )

    # -- WeasyPrint availability --
    from report.pdf import WEASYPRINT_AVAILABLE, render_pdf  # noqa: PLC0415

    if not WEASYPRINT_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail=(
                "PDF generation is not available in this environment "
                "(WeasyPrint system dependencies not installed)."
            ),
        )

    # -- Render --
    try:
        pdf_bytes = render_pdf(html)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"PDF rendering failed: {exc}",
        ) from exc

    npi = row.get("npi", "unknown")
    filename = f"medpro-report-{npi}-{report_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Id": report_id,
            "X-Report-Npi": npi,
        },
    )
