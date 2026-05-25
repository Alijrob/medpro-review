"""
routes.py — audit ledger service HTTP surface (shell).

  GET  /healthz                                  liveness
  GET  /readyz                                   readiness (reports audit DB wiring)
  POST /v1/audit/events                          append an event (computes the hashes)
  GET  /v1/audit/chains/{target_type}/{id}       the per-target chain
  GET  /v1/audit/chains/{target_type}/{id}/verify  verify that chain
  POST /v1/audit/checkpoints/{target_type}       snapshot a target_type's head
  GET  /v1/audit/verify                          verify every chain

Internal service: it is written to by other services (gateway, identity, reports,
workers), never exposed through the public gateway. In deploy it is reachable only
intra-cluster (NetworkPolicy) and writes as the medpro_audit_writer IRSA identity;
the shell leaves the endpoints unauthenticated.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from schema.v1.audit import AuditEvent, TargetType

from .config import AuditSettings, get_settings
from .ledger import AuditLedger, get_ledger
from .models import (
    AppendEventRequest,
    ChainCheckpoint,
    ChainVerification,
    LedgerVerification,
)

router = APIRouter()


@router.get("/healthz", tags=["health"])
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz", tags=["health"])
def readyz(settings: Annotated[AuditSettings, Depends(get_settings)]) -> dict:
    return {"ready": True, "audit_db_configured": settings.is_configured}


@router.post(
    "/v1/audit/events",
    tags=["audit"],
    status_code=status.HTTP_201_CREATED,
    response_model=AuditEvent,
)
def append_event(
    req: AppendEventRequest,
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
) -> AuditEvent:
    """Record one auditable action. The ledger assigns prev_event_hash + event_hash."""
    return ledger.append(
        event_type=req.event_type,
        actor_type=req.actor_type,
        target_type=req.target_type,
        target_id=req.target_id,
        action=req.action,
        actor_id=req.actor_id,
        session_id=req.session_id,
        ip_address=req.ip_address,
        user_agent=req.user_agent,
        before_hash=req.before_hash,
        after_hash=req.after_hash,
        metadata=req.metadata,
    )


@router.get(
    "/v1/audit/chains/{target_type}/{target_id}",
    tags=["audit"],
    response_model=list[AuditEvent],
)
def get_chain(
    target_type: TargetType,
    target_id: str,
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
) -> list[AuditEvent]:
    return ledger.get_chain(target_type.value, target_id)


@router.get(
    "/v1/audit/chains/{target_type}/{target_id}/verify",
    tags=["audit"],
    response_model=ChainVerification,
)
def verify_chain(
    target_type: TargetType,
    target_id: str,
    response: Response,
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
) -> ChainVerification:
    result = ledger.verify_chain(target_type.value, target_id)
    if not result.ok:
        # A tampered ledger is a compliance incident — surface it as a server error.
        response.status_code = status.HTTP_409_CONFLICT
    return result


@router.post(
    "/v1/audit/checkpoints/{target_type}",
    tags=["audit"],
    response_model=ChainCheckpoint,
    status_code=status.HTTP_201_CREATED,
)
def create_checkpoint(
    target_type: TargetType,
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
) -> ChainCheckpoint:
    checkpoint = ledger.create_checkpoint(target_type.value)
    if checkpoint is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no events for target_type '{target_type.value}' to checkpoint",
        )
    return checkpoint


@router.get("/v1/audit/verify", tags=["audit"], response_model=LedgerVerification)
def verify_all(
    response: Response,
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
) -> LedgerVerification:
    result = ledger.verify_all()
    if not result.ok:
        response.status_code = status.HTTP_409_CONFLICT
    return result
