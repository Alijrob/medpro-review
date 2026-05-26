"""
0005_report_json_storage.py

Phase 2-I: Report Generation MVP -- inline JSON + HTML persistence.

Changes to the `reports` table:
  1. Add `report_json JSONB NULL`  -- serialised ProviderReport dict
  2. Add `report_html TEXT NULL`   -- rendered HTML (inline storage; S3 in Phase 5-C)
  3. Make `user_id` nullable       -- MVP: no auth/payment yet (Phase 2-J/2-K)
  4. Make `use_agreement_id` nullable -- same; Path B agreement wired at Phase 2-J

Design notes:
  - `report_json` stores the ProviderReport model_dump(mode="json") output.
  - `report_html` stores the Jinja2-rendered HTML.  If the HTML exceeds
    REPORT_HTML_MAX_STORAGE_BYTES (default 500 KB) the field is left NULL
    and the application logs a warning.  Full S3 storage is Phase 5-C.
  - Making user_id / use_agreement_id nullable unblocks Phase 2-I pipeline
    tests where no user or agreement row exists.  The NOT NULL constraint is
    reinstated (via a data-migration + ALTER) at Phase 2-J when the payment
    flow is live.
  - FKs on user_id / use_agreement_id are RETAINED -- NULL is allowed, but if
    a non-NULL value is supplied it must reference an existing row.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. Inline report storage columns
    # -----------------------------------------------------------------
    op.add_column(
        "reports",
        sa.Column(
            "report_json",
            postgresql.JSONB,
            nullable=True,
            comment="Serialised ProviderReport dict. Populated by persist_report_activity.",
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "report_html",
            sa.Text,
            nullable=True,
            comment=(
                "Rendered HTML report. NULL if over REPORT_HTML_MAX_STORAGE_BYTES limit "
                "or not yet generated. S3 persistence is Phase 5-C."
            ),
        ),
    )

    # -----------------------------------------------------------------
    # 2. Relax NOT NULL constraints for MVP (pre-payment / pre-auth)
    # -----------------------------------------------------------------
    # Make user_id nullable (FK retained -- NULL is valid, non-NULL must ref users)
    op.alter_column("reports", "user_id", nullable=True)
    # Make use_agreement_id nullable (FK retained)
    op.alter_column("reports", "use_agreement_id", nullable=True)

    # -----------------------------------------------------------------
    # 3. Index for JSON field access patterns
    # -----------------------------------------------------------------
    op.create_index(
        "ix_reports_report_json_npi",
        "reports",
        [sa.text("(report_json->>'npi')")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_reports_report_json_npi", table_name="reports")
    op.alter_column("reports", "use_agreement_id", nullable=False)
    op.alter_column("reports", "user_id", nullable=False)
    op.drop_column("reports", "report_html")
    op.drop_column("reports", "report_json")
