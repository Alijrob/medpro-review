"""
0004_source_health_history.py

Adds the source_health_history table: an append-only time-series log of
every adapter run's SourceHealthRecord snapshot. One row per run per source.

Relationship to 0001 source_health_records:
  source_health_records  — CURRENT STATE: one row per source, upserted on each
                           health check. Indexed for fast status queries by C24.
  source_health_history  — HISTORY: append-only; never UPDATE/DELETE. One row
                           per adapter run. Used by C24 for consecutive-failure
                           accumulation, drift trends, and stale-source detection.

Also inserts the correct Phase 2-B source IDs (I1, I2, A1, A2) that were not
present in the 0003 seed (which used the pre-Phase-2-B IDs F5-F9 as placeholders).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0004"
down_revision: str = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # source_health_history
    # Append-only. INSERT via medpro_app role; no UPDATE/DELETE.
    # -----------------------------------------------------------------
    op.create_table(
        "source_health_history",
        sa.Column(
            "history_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("source_id", sa.String(20), nullable=False,
                  comment="Source code from ToS matrix (e.g. F1, I1, A1)"),
        # Run outcome
        sa.Column("status", sa.String(30), nullable=False,
                  comment="SourceStatus value at time of run"),
        sa.Column("fetch_status", sa.String(20), nullable=False,
                  comment="FetchStatus: success | partial | failed"),
        sa.Column("record_count", sa.Integer, nullable=True,
                  comment="Number of RawRecords produced by the run"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB, nullable=True,
                  comment="JSON array of error message strings"),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("retries", sa.Integer, nullable=False, server_default="0"),
        # Schema drift snapshot
        sa.Column("schema_drift_detected", sa.Boolean, nullable=False,
                  server_default="false"),
        sa.Column("schema_drift_details", sa.Text, nullable=True),
        # Accumulated counters at time of this run (maintained by C24, not base.py)
        sa.Column("accumulated_failures", sa.Integer, nullable=False, server_default="0",
                  comment="Consecutive failure count as tracked by SourceHealthMonitor"),
        sa.Column("accumulated_successes", sa.Integer, nullable=False, server_default="0",
                  comment="Consecutive success count as tracked by SourceHealthMonitor"),
        # Bulk download specifics
        sa.Column("bulk_download_record_count", sa.Integer, nullable=True),
        # Notes
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "recorded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("(NOW() AT TIME ZONE 'UTC')"),
            comment="Wall-clock time when C24 ingested this SourceHealthRecord",
        ),
    )

    # Indexes for C24 query patterns
    op.create_index(
        "ix_health_history_source_id",
        "source_health_history",
        ["source_id"],
    )
    op.create_index(
        "ix_health_history_recorded_at",
        "source_health_history",
        [sa.text("recorded_at DESC")],
    )
    op.create_index(
        "ix_health_history_status",
        "source_health_history",
        ["status"],
    )
    op.create_index(
        "ix_health_history_source_recorded",
        "source_health_history",
        ["source_id", sa.text("recorded_at DESC")],
        comment="Composite: per-source time-ordered history scan",
    )

    # -----------------------------------------------------------------
    # Seed Phase 2-B source IDs not present in the 0003 seed.
    # 0003 seeded F1-F4 (correct) and F5-F9 (pre-2-B placeholders).
    # Phase 2-B uses I1, I2, A1, A2 -- add them here.
    # F7/F8/F9 from 0003 are superseded by I1/A2/A1 but left in place
    # (ON CONFLICT DO NOTHING) to avoid altering the 0003 migration.
    # -----------------------------------------------------------------
    op.execute("""
        INSERT INTO source_health_records
            (source_id, source_name, source_category, status, updated_at)
        VALUES
            ('I1', 'CMS Medicare Enrollment',   'federal',  'unknown', NOW()),
            ('I2', 'CMS Medicaid Enrollment',   'federal',  'unknown', NOW()),
            ('A1', 'PubMed / NCBI Entrez',      'academic', 'unknown', NOW()),
            ('A2', 'ClinicalTrials.gov',         'academic', 'unknown', NOW())
        ON CONFLICT (source_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_health_history_source_recorded", "source_health_history")
    op.drop_index("ix_health_history_status", "source_health_history")
    op.drop_index("ix_health_history_recorded_at", "source_health_history")
    op.drop_index("ix_health_history_source_id", "source_health_history")
    op.drop_table("source_health_history")
    # Seed rows inserted in upgrade are left in place on downgrade
    # (idempotent with ON CONFLICT DO NOTHING; removing them would be
    # destructive if any health data has been recorded against those IDs).
