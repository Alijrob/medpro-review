"""
routes.py — API gateway HTTP surface (shell).

  GET  /healthz              liveness (no auth)
  GET  /readyz               readiness — OPA reachable when enabled
  GET  /v1/whoami            proves the shared auth overlay is mounted (auth)
  POST /v1/reports           representative downstream entry: auth + Path B + OPA + idempotency

/v1/reports is a stub (202 accepted) standing in for the Report Generation Service
(C17, Phase 2). It exists now to exercise the full gateway request chain end to end.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from .config import GatewaySettings, get_settings
from .opa import OpaUnavailable, evaluate, require_authz

# Shared auth overlay (Phase 1-F).
from backend.auth_service.dependencies import (
    get_current_user,
    require_personal_use_certified,
)
from backend.auth_service.models import AuthenticatedUser

router = APIRouter()


@router.get("/healthz", tags=["health"])
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz", tags=["health"])
def readyz(
    response: Response,
    settings: Annotated[GatewaySettings, Depends(get_settings)],
) -> dict:
    """Ready unless OPA is enabled but unreachable (fail closed)."""
    if settings.opa_enabled:
        try:
            evaluate(settings, {"probe": True})
        except OpaUnavailable as exc:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"ready": False, "reason": f"opa unreachable: {exc}"}
    return {"ready": True, "opa_enabled": settings.opa_enabled}


@router.get("/v1/whoami", tags=["identity"], response_model=AuthenticatedUser)
def whoami(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    return user


@router.post(
    "/v1/reports",
    tags=["reports"],
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_personal_use_certified)],
)
def create_report(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(require_authz("create", "report"))],
) -> dict:
    """Accept a report order. Enforces auth + Path B certification + OPA authz, and
    is idempotent via the Idempotency-Key header. Stub for the C17 report service."""
    return {
        "accepted": True,
        "request_id": getattr(request.state, "request_id", None),
        "queued_for": user.sub,
        "note": "stub — Report Generation Service (C17) lands in Phase 2",
    }
