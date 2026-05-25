"""
routes.py — auth service HTTP surface (shell).

  GET  /healthz                 liveness (no auth)
  GET  /readyz                  readiness — auth configured + JWKS reachable
  GET  /v1/me                   the current identity (auth)
  POST /v1/use-agreement        record Path B personal-use certification (auth)
  GET  /v1/reports/preflight    Path B gate demo — eligible to order a report?
  GET  /v1/admin/ping           RBAC demo — requires the `admin` role
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from . import store
from .config import AuthSettings, get_settings
from .dependencies import (
    CurrentUser,
    require_personal_use_certified,
    require_roles,
)
from .models import AuthenticatedUser, UseAgreementRequest, UseAgreementResponse
from .security import AuthError, get_jwks

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


@router.get("/healthz", tags=["health"])
def healthz() -> dict:
    """Liveness: the process is up. No auth, no external dependency."""
    return {"status": "ok"}


@router.get("/readyz", tags=["health"])
def readyz(
    response: Response,
    settings: Annotated[AuthSettings, Depends(get_settings)],
) -> dict:
    """Readiness: auth is configured and the JWKS endpoint is reachable."""
    if not settings.is_configured:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ready": False, "reason": "auth provider not configured (Entry 003 pending)"}
    try:
        get_jwks()
    except AuthError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ready": False, "reason": exc.detail}
    return {"ready": True, "auth_configured": True, "jwks_reachable": True}


@router.get("/v1/me", tags=["identity"], response_model=AuthenticatedUser)
def me(user: CurrentUser) -> AuthenticatedUser:
    """Return the identity derived from the bearer token."""
    return user


@router.post("/v1/use-agreement", tags=["identity"], response_model=UseAgreementResponse)
def post_use_agreement(
    body: UseAgreementRequest,
    user: CurrentUser,
    settings: Annotated[AuthSettings, Depends(get_settings)],
) -> UseAgreementResponse:
    """Record the Path B personal-use-only certification for the current user."""
    if not body.certified_personal_use_only:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "certified_personal_use_only must be true — the product is personal research "
            "only and may not be used for employment, credentialing, insurance, or credit "
            "decisions (DECISIONS.md Entry 004).",
        )
    agreed_at = utc_now()
    record = store.record_certification(user.sub, body.tos_version, agreed_at)
    return UseAgreementResponse(
        recorded=True,
        agreement_id=record.agreement_id,
        sub=user.sub,
        tos_version=record.tos_version,
        agreed_at=agreed_at,
        persisted=False,  # in-memory shell; Aurora use_agreements wired with DATABASE_URL
    )


@router.get("/v1/reports/preflight", tags=["path-b"])
def reports_preflight(
    user: Annotated[AuthenticatedUser, Depends(require_personal_use_certified)],
) -> dict:
    """Path B gate the gateway/report service calls before accepting a report order."""
    cert = store.get_certification(user.sub)
    return {
        "eligible": True,
        "sub": user.sub,
        "tos_version": cert.tos_version if cert else None,
    }


@router.get("/v1/admin/ping", tags=["rbac"])
def admin_ping(
    user: Annotated[AuthenticatedUser, Depends(require_roles("admin"))],
) -> dict:
    """RBAC demo endpoint — requires the `admin` role claim."""
    return {"pong": True, "sub": user.sub}
