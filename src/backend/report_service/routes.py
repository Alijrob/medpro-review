"""
routes.py -- Report Service API routes (C17 basic, Phase 2-H).

Endpoints:
    GET  /healthz                           -- liveness
    GET  /readyz                            -- readiness
    POST /v1/reports/from-profile           -- build report from a CanonicalProviderProfile body
    GET  /v1/reports/{npi}/from-profile     -- same, accepts profile as query JSON (testing only)

Note: In Phase 2-I+ these endpoints will trigger the Temporal pipeline and return
a report_id for async polling. For Phase 2-H, they accept a profile directly and
return a report synchronously (no database, no Temporal).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ValidationError

from report import build_report, render_html
from schema.v1.profile import CanonicalProviderProfile

router = APIRouter()


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
# Report endpoints
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
    summary="Build a report from a CanonicalProviderProfile",
    description=(
        "Accepts a serialised CanonicalProviderProfile and returns a ProviderReport. "
        "Phase 2-H shell -- synchronous, no persistence."
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
    summary="Build an HTML report from a CanonicalProviderProfile",
    description="Returns rendered HTML. Phase 2-H shell -- synchronous, no persistence.",
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
