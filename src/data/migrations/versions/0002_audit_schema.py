"""Audit schema — append-only audit_events table in medpro_audit database

Creates the audit_events table in the medpro_audit database.
This is a SEPARATE database from medpro — it is the append-only audit ledger
that replaces QLDB (DECISIONS.md Entry 005).

Run this migration against the AUDIT_DATABASE_URL connection, not DATABASE_URL.
The audit service (Phase 1-I) handles cross-DB writes.

Immutability enforced at 3 layers:
  1. This migration: no UPDATE/DELETE privileges granted to any application role
  2. Migration 0003: row-level security policy denying UPDATE/DELETE
  3. S3 WORM bucket: nightly hash-chained export with Object Lock COMPLIANCE

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # Extensions
    # -----------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # -----------------------------------------------------------------
    # audit_events
    #
    # Append-only. Every data write, report generation, correction,
    # access, and user action in the system emits one AuditEvent.
    #
    # Hash chaining: each row stores prev_event_hash pointing to the
    # SHA-256 hash of the previous event in the chain for that target.
    # The chain is verified by the AuditLedgerService (C5-audit).
    #
    # Written synchronously before the operation is considered committed.
    # -----------------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()"),
                  comment="Immutable primary key — never changes after INSERT"),
        sa.Column("event_type", sa.String(50), nullable=False,
                  comment="AuditEventType enum value (e.g., record.ingested, report.completed)"),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')"),
                  comment="UTC time of the event — set by the application before INSERT"),
        # Who did it
        sa.Column("actor_type", sa.String(20), nullable=False,
                  comment="ActorType: user | provider | reviewer | admin | system | api"),
        sa.Column("actor_id", sa.String(200), nullable=True,
                  comment="UUID or system ID of the actor. NULL for unauthenticated events."),
        sa.Column("session_id", sa.String(200), nullable=True,
                  comment="Request/session ID for correlating events in a single session"),
        sa.Column("ip_address", sa.String(45), nullable=True,
                  comment="IPv4 or IPv6 address of the actor"),
        sa.Column("user_agent", sa.String(500), nullable=True),
        # What was acted on
        sa.Column("target_type", sa.String(50), nullable=False,
                  comment="TargetType enum value (e.g., normalized_record, report, dispute)"),
        sa.Column("target_id", sa.String(200), nullable=False,
                  comment="UUID or identifier of the target entity"),
        sa.Column("action", sa.Text, nullable=False,
                  comment="Human-readable description of the action taken"),
        # Data change hashes
        sa.Column("before_hash", sa.String(64), nullable=True,
                  comment="SHA-256 of target state BEFORE this event (hex). NULL if no prior state."),
        sa.Column("after_hash", sa.String(64), nullable=True,
                  comment="SHA-256 of target state AFTER this event (hex). NULL if target deleted."),
        # Chain integrity (DECISIONS.md Entry 005)
        sa.Column("prev_event_hash", sa.String(64), nullable=True,
                  comment="SHA-256 of the previous AuditEvent in chain for this target. "
                           "NULL for first event in chain. Used for tamper detection."),
        sa.Column("event_hash", sa.String(64), nullable=False,
                  comment="SHA-256 of this event's canonical fields. "
                           "Computed by AuditLedgerService before INSERT. "
                           "Verified on read by AuditLedgerService."),
        # Structured metadata
        sa.Column("metadata", postgresql.JSONB, nullable=False,
                  server_default="'{}'::jsonb",
                  comment="Structured context specific to this event_type"),
    )

    # Indexes — query by target, actor, time range, event type
    op.create_index("ix_audit_events_target", "audit_events",
                    ["target_type", "target_id", "timestamp"])
    op.create_index("ix_audit_events_actor", "audit_events",
                    ["actor_type", "actor_id"])
    op.create_index("ix_audit_events_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_events_event_hash", "audit_events", ["event_hash"], unique=True,
                    comment="Enforces uniqueness of computed event hashes — tamper indicator")

    # CHECK: event_hash must be a valid SHA-256 hex digest (64 hex chars)
    op.execute("""
        ALTER TABLE audit_events
        ADD CONSTRAINT ck_event_hash_format
        CHECK (event_hash ~ '^[a-f0-9]{64}$')
    """)

    # CHECK: before/after hashes, if present, must be valid SHA-256
    op.execute("""
        ALTER TABLE audit_events
        ADD CONSTRAINT ck_before_hash_format
        CHECK (before_hash IS NULL OR before_hash ~ '^[a-f0-9]{64}$')
    """)
    op.execute("""
        ALTER TABLE audit_events
        ADD CONSTRAINT ck_after_hash_format
        CHECK (after_hash IS NULL OR after_hash ~ '^[a-f0-9]{64}$')
    """)
    op.execute("""
        ALTER TABLE audit_events
        ADD CONSTRAINT ck_prev_event_hash_format
        CHECK (prev_event_hash IS NULL OR prev_event_hash ~ '^[a-f0-9]{64}$')
    """)

    # Trigger: PREVENT any UPDATE or DELETE at the DB level
    # This is belt-and-suspenders on top of the RLS policy in migration 0003.
    op.execute("""
        CREATE OR REPLACE FUNCTION deny_audit_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_events is append-only. UPDATE and DELETE are forbidden. '
                'Event ID: %. Contact engineering if this is a legitimate data correction.',
                OLD.event_id;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_events_no_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation()
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_events_no_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation()
    """)

    # -----------------------------------------------------------------
    # audit_chain_checkpoints
    # Periodic snapshots of the hash chain head per target_type.
    # Used by AuditLedgerService to efficiently verify chain integrity
    # without scanning from genesis on every check.
    # -----------------------------------------------------------------
    op.create_table(
        "audit_chain_checkpoints",
        sa.Column("checkpoint_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("chain_head_event_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="event_id of the most recent AuditEvent in this chain at checkpoint time"),
        sa.Column("chain_head_event_hash", sa.String(64), nullable=False,
                  comment="event_hash of the chain head — verified on next chain scan"),
        sa.Column("event_count", sa.Integer, nullable=False,
                  comment="Total events in chain at checkpoint time"),
        sa.Column("checkpointed_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="Last time this checkpoint was verified by AuditLedgerService"),
        sa.Column("verification_passed", sa.Boolean, nullable=True),
    )
    op.create_index("ix_chain_checkpoints_target", "audit_chain_checkpoints",
                    ["target_type", "checkpointed_at"])


def downgrade() -> None:
    op.drop_table("audit_chain_checkpoints")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_delete ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_update ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS deny_audit_mutation()")
    op.drop_table("audit_events")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
