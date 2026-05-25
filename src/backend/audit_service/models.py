"""
models.py — API request/response models for the audit ledger service.

The persisted unit of the log is the canonical `AuditEvent` (src/schema/v1/audit.py);
these models are the HTTP surface around it. Callers never supply `event_hash` or
`prev_event_hash` — the ledger computes and assigns those (that is the whole point
of a tamper-evident chain).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from schema.v1.audit import ActorType, AuditEventType, TargetType


class AppendEventRequest(BaseModel):
    """What a service submits to record one auditable action."""

    event_type: AuditEventType
    actor_type: ActorType
    target_type: TargetType
    target_id: str = Field(..., max_length=200)
    action: str = Field(..., max_length=200)

    actor_id: str | None = Field(default=None, max_length=200)
    session_id: str | None = Field(default=None, max_length=200)
    ip_address: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=500)

    # Optional state hashes (SHA-256 hex). The ledger does not compute these — the
    # calling service hashes the target's before/after state if it wants them logged.
    before_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    after_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    metadata: dict[str, Any] = Field(default_factory=dict)


class ChainVerification(BaseModel):
    """Result of verifying one per-target hash chain."""

    target_type: str
    target_id: str
    ok: bool
    event_count: int
    head_hash: str | None = None
    broken_at_event_id: UUID | None = None
    reason: str | None = None


class LedgerVerification(BaseModel):
    """Result of verifying every chain in the ledger."""

    ok: bool
    chains_checked: int
    chains_failed: int
    failures: list[ChainVerification] = Field(default_factory=list)


class ChainCheckpoint(BaseModel):
    """Snapshot of a target_type's chain head — mirrors audit_chain_checkpoints."""

    checkpoint_id: UUID
    target_type: str
    chain_head_event_id: UUID
    chain_head_event_hash: str
    event_count: int
    checkpointed_at: datetime
    verified_at: datetime | None = None
    verification_passed: bool | None = None
