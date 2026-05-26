"""
0006_payment_columns.py

Phase 2-J: Payment Service MVP -- add Stripe Checkout tracking columns to reports.

Changes to the `reports` table:
  1. Add `stripe_checkout_session_id VARCHAR(200) NULL`
     Stores the Stripe Checkout Session ID (cs_...) so the webhook can look up
     the report row without guessing from metadata alone.

  2. Add `payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid'`
     Tracks Stripe payment state independently from the report pipeline status.
     Values: unpaid | pending | paid | refunded

     - 'unpaid'  -- report row created but no Checkout session started yet
     - 'pending' -- Checkout session created, user has not completed payment
     - 'paid'    -- checkout.session.completed received; use_agreement linked
     - 'refunded'-- Phase 5-G

Design notes:
  - `stripe_checkout_session_id` is indexed for fast O(1) webhook lookup.
  - `payment_status` is separate from `reports.status` (pipeline state).
    A report can be `status='complete'` (pipeline done) with `payment_status='unpaid'`
    (free tier) or `payment_status='paid'` (standard consumer flow).
  - The `reports.user_id` and `reports.use_agreement_id` nullable columns from
    migration 0005 are backfilled by the webhook handler (POST /v1/payments/webhook)
    when `checkout.session.completed` fires.  They stay nullable until Phase 2-K
    enforces auth.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. Stripe Checkout Session ID for webhook lookup
    # -----------------------------------------------------------------
    op.add_column(
        "reports",
        sa.Column(
            "stripe_checkout_session_id",
            sa.String(200),
            nullable=True,
            comment=(
                "Stripe Checkout Session ID (cs_...). Set by POST /v1/payments/checkout. "
                "Used by webhook handler to look up the reports row."
            ),
        ),
    )
    op.create_index(
        "ix_reports_stripe_session_id",
        "reports",
        ["stripe_checkout_session_id"],
        unique=True,
        postgresql_where=sa.text("stripe_checkout_session_id IS NOT NULL"),
    )

    # -----------------------------------------------------------------
    # 2. Payment status (independent of pipeline status)
    # -----------------------------------------------------------------
    op.add_column(
        "reports",
        sa.Column(
            "payment_status",
            sa.String(20),
            nullable=False,
            server_default="'unpaid'",
            comment="Stripe payment state: unpaid | pending | paid | refunded",
        ),
    )
    op.create_index(
        "ix_reports_payment_status",
        "reports",
        ["payment_status"],
    )

    # DB-level constraint on allowed values
    op.execute("""
        ALTER TABLE reports
        ADD CONSTRAINT ck_reports_payment_status
        CHECK (payment_status IN ('unpaid', 'pending', 'paid', 'refunded'))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE reports DROP CONSTRAINT IF EXISTS ck_reports_payment_status")
    op.drop_index("ix_reports_payment_status", table_name="reports")
    op.drop_column("reports", "payment_status")
    op.drop_index("ix_reports_stripe_session_id", table_name="reports")
    op.drop_column("reports", "stripe_checkout_session_id")
