"""
audit.py — Immutable append-only audit log models.

Replaces QLDB (per DECISIONS.md Entry 005). Implemented in Aurora as append-only
tables (row-level security blocks UPDATE and DELETE on audit rows) with SHA-256
hash-chaining to maintain a tamper-evident chain of custody.

The AuditEvent model is the unit of the log. The chain is maintained by the
AuditLedgerService (C5-audit), not by this model.

Every data write, report generation, correction, access, and user action in
the system emits an AuditEvent. These are written synchronously before the
operation is considered committed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from .common import ImmutableRecord, new_uuid, utc_now


# ---------------------------------------------------------------------------
# Event type taxonomy
# ---------------------------------------------------------------------------


class AuditEventType(str, Enum):
    """
    All auditable event types in the system. Grouped by domain.
    Add new types here — never remove or rename existing types.
    """

    # --- Data ingestion ---
    RECORD_INGESTED = "record.ingested"                 # NormalizedRecord written for the first time
    RECORD_UPDATED = "record.updated"                   # NormalizedRecord re-ingested with changes
    RECORD_STATUS_CHANGED = "record.status_changed"     # VerificationStatus changed
    RECORD_REMOVED = "record.removed"                   # Record soft-deleted (source retracted/expunged)

    # --- Profile lifecycle ---
    PROFILE_CREATED = "profile.created"                 # CanonicalProviderProfile first created
    PROFILE_UPDATED = "profile.updated"                 # Profile rebuilt after new source data
    PROFILE_FLAGGED = "profile.flagged"                 # has_pending_corrections set to True

    # --- Identity resolution ---
    BUNDLE_CREATED = "bundle.created"                   # UnifiedIdBundle created
    BUNDLE_UPDATED = "bundle.updated"                   # Bundle updated with new contributing source
    BUNDLE_HUMAN_REVIEW = "bundle.human_review"         # Bundle flagged for HitL review
    BUNDLE_HUMAN_RESOLVED = "bundle.human_resolved"     # HitL review completed

    # --- Reports ---
    REPORT_REQUESTED = "report.requested"               # User submitted a report request
    REPORT_STARTED = "report.started"                   # Temporal workflow launched
    REPORT_COMPLETED = "report.completed"               # Report generation finished
    REPORT_PARTIAL = "report.partial"                   # Report delivered as partial
    REPORT_FAILED = "report.failed"                     # Report generation failed
    REPORT_ACCESSED = "report.accessed"                 # User accessed the report
    REPORT_EXPIRED = "report.expired"                   # Report TTL reached

    # --- Disputes / corrections ---
    DISPUTE_SUBMITTED = "dispute.submitted"             # New Dispute record created
    DISPUTE_ASSIGNED = "dispute.assigned"               # Reviewer assigned
    DISPUTE_RESOLVED = "dispute.resolved"               # Dispute closed with a resolution
    DISPUTE_CORRECTION_APPLIED = "dispute.correction_applied"  # Underlying data updated

    # --- User account ---
    USER_CREATED = "user.created"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_AGREEMENT_SIGNED = "user.agreement_signed"     # Path B ToS certification
    USER_DELETION_REQUESTED = "user.deletion_requested" # CCPA deletion request
    USER_DELETION_APPLIED = "user.deletion_applied"     # PII zeroed

    # --- Provider profile claim ---
    PROVIDER_CLAIM_SUBMITTED = "provider.claim_submitted"
    PROVIDER_CLAIM_VERIFIED = "provider.claim_verified"
    PROVIDER_CLAIM_REJECTED = "provider.claim_rejected"

    # --- Payment ---
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_REFUNDED = "payment.refunded"

    # --- Source health ---
    SOURCE_HEALTH_ALERT = "source.health_alert"         # Source went down or schema drifted
    SOURCE_HEALTH_RECOVERED = "source.health_recovered"

    # --- Administrative ---
    ADMIN_RECORD_OVERRIDE = "admin.record_override"     # Admin manually overrides a record
    ADMIN_PROFILE_REBUILD = "admin.profile_rebuild"     # Admin triggered a profile rebuild
    ADMIN_USER_MODIFIED = "admin.user_modified"


class ActorType(str, Enum):
    """Who or what triggered this audit event."""

    USER = "user"               # A registered consumer user
    PROVIDER = "provider"       # A physician acting on their own profile
    REVIEWER = "reviewer"       # An internal HitL reviewer
    ADMIN = "admin"             # An internal admin
    SYSTEM = "system"           # An automated system process (Temporal, cron, adapter)
    API = "api"                 # An authenticated API caller


class TargetType(str, Enum):
    """The type of entity the audit event acted on."""

    NORMALIZED_RECORD = "normalized_record"
    CANONICAL_PROFILE = "canonical_profile"
    UNIFIED_ID_BUNDLE = "unified_id_bundle"
    REPORT = "report"
    DISPUTE = "dispute"
    USER = "user"
    SOURCE = "source"
    PAYMENT = "payment"
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# AuditEvent — the unit of the append-only log
# ---------------------------------------------------------------------------


class AuditEvent(ImmutableRecord):
    """
    A single entry in the append-only audit log.

    Immutable once written. The Aurora implementation enforces this via
    row-level security (no UPDATE or DELETE on the audit_events table).

    Hash chaining: each event stores the hash of the previous event in this
    chain (prev_event_hash), enabling detection of any tampering with the log.
    The chain is computed and verified by the AuditLedgerService, not here.
    """

    event_id: UUID = Field(default_factory=new_uuid)
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=utc_now)

    # --- Who did it ---
    actor_type: ActorType
    actor_id: str | None = Field(
        default=None,
        max_length=200,
        description="UUID or system identifier of the actor. None for unauthenticated events.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=200,
        description="Session or request ID (for correlating events in a single user session).",
    )
    ip_address: str | None = Field(
        default=None,
        max_length=45,
        description="IPv4 or IPv6 address of the actor.",
    )
    user_agent: str | None = Field(default=None, max_length=500)

    # --- What was acted on ---
    target_type: TargetType
    target_id: str = Field(
        ...,
        max_length=200,
        description="UUID or identifier of the target entity.",
    )
    action: str = Field(
        ...,
        max_length=200,
        description="Human-readable description of the action taken.",
        examples=[
            "NormalizedRecord ingested from NPPES bulk download",
            "Dispute resolved: data verified as accurate",
            "Report delivered to user",
        ],
    )

    # --- Data change hashes ---
    before_hash: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hash of the target's state BEFORE this event (if applicable).",
    )
    after_hash: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hash of the target's state AFTER this event (if applicable).",
    )

    # --- Chain integrity ---
    prev_event_hash: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description=(
            "SHA-256 hash of the previous AuditEvent in the chain for this target. "
            "None for the first event in a chain. Used for tamper detection."
        ),
    )
    event_hash: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description=(
            "SHA-256 hash of this event's canonical fields (excluding event_hash itself). "
            "Computed by AuditLedgerService before write."
        ),
    )

    # --- Structured metadata ---
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured context specific to this event type. "
            "Schema varies by event_type — see AuditLedgerService for per-type schemas."
        ),
    )

    @classmethod
    def compute_hash(cls, event: "AuditEvent") -> str:
        """
        Compute SHA-256 hash of the canonical audit event fields.
        Excludes event_hash (it contains the hash of its own fields).
        Called by AuditLedgerService before persisting.
        """
        canonical = {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "actor_type": event.actor_type.value,
            "actor_id": event.actor_id,
            "target_type": event.target_type.value,
            "target_id": event.target_id,
            "action": event.action,
            "before_hash": event.before_hash,
            "after_hash": event.after_hash,
            "prev_event_hash": event.prev_event_hash,
        }
        serialized = json.dumps(canonical, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()
