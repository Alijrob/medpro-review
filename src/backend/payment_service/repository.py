"""
repository.py -- PaymentRepository: DB operations for the Payment Service (Phase 2-J).

Covers three tables: reports, users, use_agreements.

Key operations:
    get_report_row(report_id)               -- SELECT report row for pre-payment validation
    set_checkout_session(report_id, sid)    -- UPDATE stripe_checkout_session_id + payment_status='pending'
    get_report_by_session(session_id)       -- SELECT report by stripe_checkout_session_id (webhook lookup)
    complete_payment(...)                   -- UPDATE payment fields + backfill user_id/use_agreement_id
    upsert_user(email)                      -- INSERT user row by email (ON CONFLICT DO NOTHING), return UUID
    create_use_agreement(...)               -- INSERT use_agreements row, return UUID

All operations use text() SQL (same pattern as ReportRepository -- avoids pulling in
the full ORM model class which depends on psycopg2).  Safe to import without a live DB.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa

log = logging.getLogger(__name__)


class PaymentRepository:
    """
    Sync SQLAlchemy wrapper around the payment-related tables.

    Construct with a live database URL.  Check `is_configured` before using.
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        if database_url:
            self._engine: sa.engine.Engine | None = sa.create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        else:
            self._engine = None

    @property
    def is_configured(self) -> bool:
        return self._engine is not None

    # ------------------------------------------------------------------
    # reports table
    # ------------------------------------------------------------------

    def get_report_row(self, report_id: UUID) -> dict | None:
        """
        SELECT the minimal columns needed for payment validation.
        Returns None if not found.
        """
        if self._engine is None:
            raise RuntimeError("PaymentRepository: database not configured.")

        with self._engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    """
                    SELECT report_id, provider_npi, status, payment_status,
                           stripe_checkout_session_id, user_id, use_agreement_id
                      FROM reports
                     WHERE report_id = :rid
                    """
                ),
                {"rid": str(report_id)},
            ).fetchone()

        if row is None:
            return None

        return {
            "report_id": str(row.report_id),
            "npi": row.provider_npi,
            "status": row.status,
            "payment_status": row.payment_status,
            "stripe_checkout_session_id": row.stripe_checkout_session_id,
            "user_id": str(row.user_id) if row.user_id else None,
            "use_agreement_id": str(row.use_agreement_id) if row.use_agreement_id else None,
        }

    def set_checkout_session(self, report_id: UUID, session_id: str) -> None:
        """
        UPDATE the report row to record the Stripe Checkout Session ID and
        advance payment_status from 'unpaid' to 'pending'.
        """
        if self._engine is None:
            raise RuntimeError("PaymentRepository: database not configured.")

        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    UPDATE reports
                       SET stripe_checkout_session_id = :sid,
                           payment_status = 'pending'
                     WHERE report_id = :rid
                    """
                ),
                {"sid": session_id, "rid": str(report_id)},
            )
        log.debug(
            "PaymentRepository.set_checkout_session: report_id=%s session_id=%s",
            report_id, session_id,
        )

    def get_report_by_session(self, session_id: str) -> dict | None:
        """
        SELECT report row by Stripe Checkout Session ID.
        Used by the webhook handler to look up which report was purchased.
        """
        if self._engine is None:
            raise RuntimeError("PaymentRepository: database not configured.")

        with self._engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    """
                    SELECT report_id, provider_npi, payment_status, user_id, use_agreement_id
                      FROM reports
                     WHERE stripe_checkout_session_id = :sid
                    """
                ),
                {"sid": session_id},
            ).fetchone()

        if row is None:
            return None

        return {
            "report_id": str(row.report_id),
            "npi": row.provider_npi,
            "payment_status": row.payment_status,
            "user_id": str(row.user_id) if row.user_id else None,
            "use_agreement_id": str(row.use_agreement_id) if row.use_agreement_id else None,
        }

    def complete_payment(
        self,
        report_id: UUID,
        stripe_payment_intent_id: str,
        price_paid_usd: Decimal,
        user_id: UUID,
        use_agreement_id: UUID,
    ) -> None:
        """
        Mark payment_status='paid' and backfill user_id, use_agreement_id,
        stripe_payment_intent_id, price_paid_usd on the report row.
        """
        if self._engine is None:
            raise RuntimeError("PaymentRepository: database not configured.")

        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    UPDATE reports
                       SET payment_status            = 'paid',
                           user_id                   = :user_id,
                           use_agreement_id          = :agreement_id,
                           stripe_payment_intent_id  = :pi_id,
                           price_paid_usd            = :price
                     WHERE report_id = :rid
                    """
                ),
                {
                    "user_id": str(user_id),
                    "agreement_id": str(use_agreement_id),
                    "pi_id": stripe_payment_intent_id,
                    "price": str(price_paid_usd),
                    "rid": str(report_id),
                },
            )
        log.info(
            "PaymentRepository.complete_payment: report_id=%s payment_intent=%s",
            report_id, stripe_payment_intent_id,
        )

    # ------------------------------------------------------------------
    # users table
    # ------------------------------------------------------------------

    def upsert_user(self, email: str) -> UUID:
        """
        INSERT a minimal user row by email.  If a row with that email already
        exists (from a previous purchase or Phase 2-K sign-up), do nothing and
        return the existing user_id.

        auth_provider_sub is left NULL -- Phase 2-K links the Auth0 account.
        """
        if self._engine is None:
            raise RuntimeError("PaymentRepository: database not configured.")

        user_id = uuid4()
        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO users (user_id, email, role, is_active, is_email_verified)
                    VALUES (:uid, :email, 'consumer', true, false)
                    ON CONFLICT (email) DO NOTHING
                    """
                ),
                {"uid": str(user_id), "email": email},
            )
            # Retrieve the canonical user_id (may differ from our generated one
            # if the INSERT was a no-op due to conflict)
            row = conn.execute(
                sa.text("SELECT user_id FROM users WHERE email = :email"),
                {"email": email},
            ).fetchone()

        if row is None:
            raise RuntimeError(
                f"PaymentRepository.upsert_user: could not find or create user for email={email!r}"
            )

        canonical_id = UUID(str(row.user_id))
        log.debug("PaymentRepository.upsert_user: email=%s user_id=%s", email, canonical_id)
        return canonical_id

    def link_auth_sub(self, email: str, auth_provider_sub: str) -> "UUID | None":
        """
        Link an Auth0 sub to an existing users row identified by email.

        UPDATE users SET auth_provider_sub = :sub WHERE email = :email
            AND auth_provider_sub IS NULL

        Idempotent: if auth_provider_sub is already set to the same value,
        the UPDATE is a no-op and we still return the user_id.

        Returns the user_id UUID if the row exists (whether or not the UPDATE
        changed anything), or None if no row with that email is found.
        """
        if self._engine is None:
            raise RuntimeError("PaymentRepository: database not configured.")

        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    UPDATE users
                       SET auth_provider_sub = :sub
                     WHERE email = :email
                       AND auth_provider_sub IS NULL
                    """
                ),
                {"sub": auth_provider_sub, "email": email},
            )
            row = conn.execute(
                sa.text("SELECT user_id FROM users WHERE email = :email"),
                {"email": email},
            ).fetchone()

        if row is None:
            log.debug("PaymentRepository.link_auth_sub: no user found for email=%s", email)
            return None

        canonical_id = UUID(str(row.user_id))
        log.debug(
            "PaymentRepository.link_auth_sub: email=%s user_id=%s sub=%s",
            email, canonical_id, auth_provider_sub,
        )
        return canonical_id

    # ------------------------------------------------------------------
    # use_agreements table
    # ------------------------------------------------------------------

    def create_use_agreement(
        self,
        user_id: UUID,
        tos_version: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UUID:
        """
        INSERT a new use_agreements row (certified_personal_use_only=True is
        hard-coded because the Path B checkout flow requires it -- the requester
        certified at checkout creation time).
        """
        if self._engine is None:
            raise RuntimeError("PaymentRepository: database not configured.")

        agreement_id = uuid4()
        agreed_at = datetime.now(tz=timezone.utc)

        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO use_agreements
                        (agreement_id, user_id, tos_version, agreed_at,
                         ip_address, user_agent, certified_personal_use_only)
                    VALUES
                        (:aid, :uid, :tos, :agreed_at,
                         :ip, :ua, true)
                    """
                ),
                {
                    "aid": str(agreement_id),
                    "uid": str(user_id),
                    "tos": tos_version,
                    "agreed_at": agreed_at,
                    "ip": ip_address,
                    "ua": user_agent,
                },
            )

        log.debug(
            "PaymentRepository.create_use_agreement: user_id=%s agreement_id=%s",
            user_id, agreement_id,
        )
        return agreement_id
