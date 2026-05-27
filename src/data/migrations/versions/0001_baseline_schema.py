"""Baseline schema — main medpro database tables

Creates all tables for the medpro database (not the audit database).
Tables are derived directly from the Phase 1-A Pydantic v2 schema models.

Revision ID: 0001
Revises: (none)
Create Date: 2026-05-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # Extensions (required for UUID primary keys and JSONB)
    # -----------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')  # trigram index for name search

    # -----------------------------------------------------------------
    # updated_at auto-update trigger function
    # -----------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # -----------------------------------------------------------------
    # unified_id_bundles
    # One row per NPI. The output of C12 (Identity Resolution Engine).
    # Primary anchor for all data in the system.
    # -----------------------------------------------------------------
    op.create_table(
        "unified_id_bundles",
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("primary_npi", sa.String(10), nullable=False, unique=True,
                  comment="10-digit NPI — canonical provider identifier"),
        sa.Column("entity_type", sa.String(20), nullable=False,
                  comment="'individual' or 'organization'"),
        sa.Column("primary_name", postgresql.JSONB, nullable=False,
                  comment="ProviderName: {first, last, middle, prefix, suffix, credentials}"),
        sa.Column("name_variants", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb"),
                  comment="All other name forms seen across sources"),
        sa.Column("gender", sa.String(1), nullable=False, server_default=sa.text("'U'")),
        sa.Column("primary_specialty", postgresql.JSONB, nullable=True,
                  comment="TaxonomyCode from NPPES primary taxonomy"),
        sa.Column("all_taxonomies", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("known_addresses", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("other_identifiers", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb"),
                  comment="DEA, state license numbers, UPIN, etc."),
        sa.Column("identity_confidence", sa.Numeric(4, 3), nullable=False,
                  comment="0.000-1.000. Target: >0.980 per architecture criteria."),
        sa.Column("contributing_sources", postgresql.ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'"),
                  comment="Source IDs (e.g., F1, F2, S5) that contributed to this bundle"),
        sa.Column("human_review_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("human_review_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("last_full_refresh_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_unified_id_bundles_primary_npi", "unified_id_bundles", ["primary_npi"])
    op.create_index("ix_unified_id_bundles_human_review",
                    "unified_id_bundles", ["human_review_required"],
                    postgresql_where=sa.text("human_review_required = true"))
    op.execute("""
        CREATE TRIGGER trg_unified_id_bundles_updated_at
        BEFORE UPDATE ON unified_id_bundles
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # -----------------------------------------------------------------
    # normalized_records
    # One row per source record per provider. Raw source data after normalization.
    # Output of C11 (Normalization Layer).
    # -----------------------------------------------------------------
    op.create_table(
        "normalized_records",
        sa.Column("record_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("primary_npi", sa.String(10), nullable=False,
                  comment="FK to unified_id_bundles.primary_npi"),
        sa.Column("source_id", sa.String(20), nullable=False,
                  comment="Source code (e.g., F1=NPPES, F2=OIG, S5=CA Board)"),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_category", sa.String(50), nullable=False,
                  comment="SourceCategory enum value"),
        sa.Column("source_record_id", sa.String(200), nullable=True,
                  comment="Record identifier within the source system"),
        sa.Column("record_type", sa.String(50), nullable=False,
                  comment="Discriminator for NormalizedRecord subtype (license, exclusion, court, etc.)"),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'"),
                  comment="VerificationStatus enum value"),
        sa.Column("raw_record_hash", sa.String(64), nullable=False,
                  comment="SHA-256 of raw record before normalization — deduplication key"),
        sa.Column("data", postgresql.JSONB, nullable=False,
                  comment="Full normalized record fields (schema varies by record_type)"),
        sa.Column("provenance", postgresql.JSONB, nullable=False,
                  comment="DataProvenance: source, ingested_at, raw_record_hash, schema_version"),
        sa.Column("schema_version", sa.String(10), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("ingested_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("source_as_of", sa.Date, nullable=True,
                  comment="Date the source data was current as of"),
    )
    op.create_index("ix_normalized_records_npi", "normalized_records", ["primary_npi"])
    op.create_index("ix_normalized_records_source", "normalized_records",
                    ["source_id", "source_category"])
    op.create_index("ix_normalized_records_hash", "normalized_records", ["raw_record_hash"],
                    unique=True)  # Deduplication -- prevents re-ingesting identical raw records
    op.create_index("ix_normalized_records_status", "normalized_records", ["status"])
    op.create_index("ix_normalized_records_type", "normalized_records", ["record_type"])
    op.create_foreign_key(
        "fk_normalized_records_npi",
        "normalized_records", "unified_id_bundles",
        ["primary_npi"], ["primary_npi"],
        ondelete="RESTRICT",
    )

    # -----------------------------------------------------------------
    # canonical_provider_profiles
    # One row per NPI. The merged, provenance-tagged read model.
    # Rebuilt by C13 (Entity Linking & Merge) after each ingest cycle.
    # -----------------------------------------------------------------
    op.create_table(
        "canonical_provider_profiles",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("primary_npi", sa.String(10), nullable=False, unique=True,
                  comment="FK to unified_id_bundles.primary_npi"),
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="FK to unified_id_bundles.bundle_id"),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("report_disclaimer_required", sa.Boolean, nullable=False, server_default="true",
                  comment="Path B: always True — disclaimer shown on every report"),
        # Full profile stored as JSONB (CanonicalProviderProfile Pydantic model serialized)
        sa.Column("profile_data", postgresql.JSONB, nullable=False,
                  comment="Full CanonicalProviderProfile serialized as JSONB"),
        sa.Column("source_coverage_count", sa.Integer, nullable=True,
                  comment="Number of distinct source categories in this profile"),
        sa.Column("has_pending_corrections", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_rebuilt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
    )
    op.create_index("ix_canonical_profiles_npi", "canonical_provider_profiles", ["primary_npi"])
    op.create_index("ix_canonical_profiles_corrections",
                    "canonical_provider_profiles", ["has_pending_corrections"],
                    postgresql_where=sa.text("has_pending_corrections = true"))
    op.create_foreign_key(
        "fk_canonical_profiles_npi",
        "canonical_provider_profiles", "unified_id_bundles",
        ["primary_npi"], ["primary_npi"],
        ondelete="RESTRICT",
    )
    op.execute("""
        CREATE TRIGGER trg_canonical_profiles_updated_at
        BEFORE UPDATE ON canonical_provider_profiles
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # -----------------------------------------------------------------
    # users
    # Consumer accounts. PII zeroed on CCPA deletion request (soft delete).
    # -----------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(20), nullable=False, server_default=sa.text("'consumer'"),
                  comment="UserRole: consumer | provider | admin | reviewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("auth_provider_sub", sa.String(200), nullable=True, unique=True,
                  comment="Auth0/Okta subject claim"),
        sa.Column("claimed_provider_npi", sa.String(10), nullable=True,
                  comment="Set if role=provider and user has claimed an NPI profile"),
        sa.Column("provider_claim_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="CCPA soft delete — set when PII is zeroed"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_auth_sub", "users", ["auth_provider_sub"])
    op.create_index("ix_users_active", "users", ["is_active"],
                    postgresql_where=sa.text("is_active = true"))

    # -----------------------------------------------------------------
    # use_agreements
    # Path B ToS certification. Required before any report purchase.
    # Append-only in practice — users never delete past agreements.
    # -----------------------------------------------------------------
    op.create_table(
        "use_agreements",
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="FK to users.user_id"),
        sa.Column("tos_version", sa.String(20), nullable=False,
                  comment="ToS version agreed to (e.g., tos-v1.0)"),
        sa.Column("agreed_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("ip_address", sa.String(45), nullable=True,
                  comment="IPv4 or IPv6 at time of agreement — legal evidence"),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("certified_personal_use_only", sa.Boolean, nullable=False,
                  comment="MUST be true — Path B certification"),
    )
    op.create_index("ix_use_agreements_user", "use_agreements", ["user_id"])
    op.create_foreign_key(
        "fk_use_agreements_user",
        "use_agreements", "users",
        ["user_id"], ["user_id"],
        ondelete="CASCADE",
    )
    # Enforce Path B at DB level — agreement cannot be inserted with False
    op.execute("""
        ALTER TABLE use_agreements
        ADD CONSTRAINT ck_certified_personal_use_only
        CHECK (certified_personal_use_only = true)
    """)

    # -----------------------------------------------------------------
    # reports
    # Report request lifecycle + output metadata.
    # Report content (HTML/PDF/JSON) lives in S3 at report_s3_key.
    # -----------------------------------------------------------------
    op.create_table(
        "reports",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_npi", sa.String(10), nullable=False),
        sa.Column("report_type", sa.String(20), nullable=False, server_default=sa.text("'comprehensive'"),
                  comment="ReportType: comprehensive | partial | refresh"),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'queued'"),
                  comment="ReportStatus: queued | in_progress | partial | complete | failed | expired"),
        # Path B enforcement
        sa.Column("use_agreement_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="FK to use_agreements — report cannot exist without valid Path B certification"),
        sa.Column("tos_version_at_purchase", sa.String(20), nullable=False),
        # Temporal workflow
        sa.Column("temporal_workflow_id", sa.String(200), nullable=True),
        # Source tracking
        sa.Column("sources_attempted", postgresql.ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("sources_succeeded", postgresql.ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("sources_failed", postgresql.ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("is_partial", sa.Boolean, nullable=False, server_default="false"),
        # Output
        sa.Column("report_s3_key", sa.String(500), nullable=True),
        sa.Column("profile_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="FK to canonical_provider_profiles.profile_id (snapshot at report time)"),
        # Payment
        sa.Column("price_paid_usd", sa.Numeric(10, 2), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(100), nullable=True),
        # Timestamps
        sa.Column("requested_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_user", "reports", ["user_id"])
    op.create_index("ix_reports_provider_npi", "reports", ["provider_npi"])
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_requested_at", "reports", ["requested_at"])
    op.create_foreign_key("fk_reports_user", "reports", "users",
                          ["user_id"], ["user_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_reports_agreement", "reports", "use_agreements",
                          ["use_agreement_id"], ["agreement_id"], ondelete="RESTRICT")

    # -----------------------------------------------------------------
    # disputes
    # Data correction requests (Path B simplified workflow).
    # No FCRA § 1681i legal SLA. Internal 30-day target only.
    # -----------------------------------------------------------------
    op.create_table(
        "disputes",
        sa.Column("dispute_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="FK to reports — nullable if provider submits directly"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="FK to users — nullable for provider-submitted disputes"),
        sa.Column("provider_npi", sa.String(10), nullable=False),
        sa.Column("submitter_type", sa.String(20), nullable=False, server_default=sa.text("'consumer'"),
                  comment="'consumer' or 'provider'"),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'submitted'"),
                  comment="DisputeStatus enum value"),
        sa.Column("flagged_fields", postgresql.JSONB, nullable=False,
                  comment="List of DisputeField: field_path, reported_value, claimed_correct_value"),
        sa.Column("description", sa.Text, nullable=False),
        # Review
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="FK to users (role=reviewer)"),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Resolution
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("corrected_record_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("correction_applied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Timestamps
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("target_resolution_date", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="Voluntary 30-day target — NOT a legal deadline on Path B"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
    )
    op.create_index("ix_disputes_provider_npi", "disputes", ["provider_npi"])
    op.create_index("ix_disputes_status", "disputes", ["status"])
    op.create_index("ix_disputes_user", "disputes", ["user_id"])
    op.create_foreign_key("fk_disputes_report", "disputes", "reports",
                          ["report_id"], ["report_id"], ondelete="SET NULL")
    op.create_foreign_key("fk_disputes_user", "disputes", "users",
                          ["user_id"], ["user_id"], ondelete="SET NULL")
    op.execute("""
        CREATE TRIGGER trg_disputes_updated_at
        BEFORE UPDATE ON disputes
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # -----------------------------------------------------------------
    # source_health_records
    # One row per data source. Upserted after each health check.
    # Output of C24 (Source Health Monitor).
    # -----------------------------------------------------------------
    op.create_table(
        "source_health_records",
        sa.Column("health_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_id", sa.String(20), nullable=False, unique=True,
                  comment="Source code from ToS matrix (e.g., F1=NPPES, F2=OIG)"),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_category", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'unknown'"),
                  comment="SourceStatus enum value"),
        # Availability
        sa.Column("last_checked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_successful_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_successes", sa.Integer, nullable=False, server_default="0"),
        # Performance
        sa.Column("avg_latency_ms", sa.Float, nullable=True),
        sa.Column("p95_latency_ms", sa.Float, nullable=True),
        sa.Column("error_rate_1h", sa.Float, nullable=True),
        sa.Column("requests_last_1h", sa.Integer, nullable=True),
        # Schema drift
        sa.Column("expected_schema_version", sa.String(20), nullable=True),
        sa.Column("detected_schema_version", sa.String(20), nullable=True),
        sa.Column("schema_drift_detected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("schema_drift_details", sa.Text, nullable=True),
        sa.Column("schema_drift_first_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Bulk download tracking
        sa.Column("last_bulk_download_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("bulk_download_record_count", sa.Integer, nullable=True),
        sa.Column("bulk_download_expected_min", sa.Integer, nullable=True),
        # Ops
        sa.Column("alert_suppressed_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
    )
    op.create_index("ix_source_health_source_id", "source_health_records", ["source_id"])
    op.create_index("ix_source_health_status", "source_health_records", ["status"])
    op.create_index("ix_source_health_drift",
                    "source_health_records", ["schema_drift_detected"],
                    postgresql_where=sa.text("schema_drift_detected = true"))
    op.execute("""
        CREATE TRIGGER trg_source_health_updated_at
        BEFORE UPDATE ON source_health_records
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # -----------------------------------------------------------------
    # derived_signals
    # Computed risk/quality signals per provider.
    # Output of C16 (Analytics & Anomaly Detection).
    # All signals require a human-readable explanation (architecture criterion).
    # -----------------------------------------------------------------
    op.create_table(
        "derived_signals",
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("provider_npi", sa.String(10), nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False,
                  comment="DerivedSignalType enum value"),
        sa.Column("value", sa.Float, nullable=False,
                  comment="0.0-1.0. Flags: 1.0=True/0.0=False. Scores: 0.0=low/1.0=high."),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("explanation", sa.Text, nullable=False,
                  comment="Required plain-English explanation suitable for report display"),
        sa.Column("contributing_sources", postgresql.ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("contributing_record_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default=sa.text("'{}'")),
        sa.Column("model_version", sa.String(50), nullable=False, server_default=sa.text("'rule-v1'")),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'UTC')")),
        sa.Column("valid_until", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_derived_signals_npi", "derived_signals", ["provider_npi"])
    op.create_index("ix_derived_signals_type", "derived_signals",
                    ["provider_npi", "signal_type"], unique=True)  # One active signal per type per provider
    op.create_index("ix_derived_signals_valid",
                    "derived_signals", ["valid_until"],
                    postgresql_where=sa.text("valid_until IS NOT NULL"))
    op.create_foreign_key(
        "fk_derived_signals_npi",
        "derived_signals", "unified_id_bundles",
        ["provider_npi"], ["primary_npi"],
        ondelete="CASCADE",
    )
    # Enforce explanation is non-empty at DB level
    op.execute("""
        ALTER TABLE derived_signals
        ADD CONSTRAINT ck_explanation_nonempty
        CHECK (length(trim(explanation)) >= 10)
    """)


def downgrade() -> None:
    op.drop_table("derived_signals")
    op.drop_table("source_health_records")
    op.drop_table("disputes")
    op.drop_table("reports")
    op.drop_table("use_agreements")
    op.drop_table("users")
    op.drop_table("canonical_provider_profiles")
    op.drop_table("normalized_records")
    op.drop_table("unified_id_bundles")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
