"""
models.py -- Request/Response Pydantic models for the Payment Service (Phase 2-J).
"""
from __future__ import annotations

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# POST /v1/payments/checkout
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    """Request body for POST /v1/payments/checkout."""

    report_id: str
    """UUID of the report row created by POST /v1/reports/request."""

    npi: str
    """10-digit NPI being researched."""

    success_url: str
    """URL Stripe redirects to after successful payment.
    May contain the {CHECKOUT_SESSION_ID} template variable."""

    cancel_url: str
    """URL Stripe redirects to if the user abandons checkout."""

    certified_personal_use_only: bool
    """MUST be True. Path B certification: the requester certifies they are
    purchasing this report for personal use only, not for employment screening,
    credit decisions, or any purpose governed by FCRA."""

    customer_email: str | None = None
    """Optional: pre-fill the Stripe Checkout form with the customer's email."""

    @field_validator("certified_personal_use_only")
    @classmethod
    def must_certify_personal_use(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "certified_personal_use_only must be True. "
                "You must certify personal use only to purchase a report."
            )
        return v


class CheckoutResponse(BaseModel):
    """Response envelope for POST /v1/payments/checkout."""

    checkout_url: str
    """Stripe-hosted Checkout page URL. Redirect the user here."""

    session_id: str
    """Stripe Checkout Session ID (cs_...). Store client-side for success-page retrieval."""

    report_id: str
    """The report_id passed in the request (echo for correlation)."""

    stripe_configured: bool
    """True when a real Stripe session was created. False in unconfigured/test mode."""


# ---------------------------------------------------------------------------
# POST /v1/payments/webhook
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# POST /v1/users/sync
# ---------------------------------------------------------------------------


class UserSyncRequest(BaseModel):
    """Request body for POST /v1/users/sync.

    Called server-to-server from the Next.js afterCallback hook after a
    successful Auth0 login.  Links the Auth0 sub to an existing users row
    (created by the Stripe webhook) or creates a new user row.

    No JWT validation at this endpoint -- the call originates from the
    Next.js server process (trusted network boundary); adding JWT validation
    here would duplicate auth_service logic (DECISIONS.md Entry 033).
    """

    email: str
    """Auth0 profile email.  Used to locate or create the users row."""

    auth_provider_sub: str
    """Auth0 subject claim (sub).  e.g. 'auth0|64abc...'"""


class UserSyncResponse(BaseModel):
    """Response for POST /v1/users/sync."""

    user_id: str | None = None
    """UUID of the users row that was found or created.  None when DB not configured."""

    linked: bool
    """True when auth_provider_sub was written to the row.
    False when the email was not found, the sub was already set (idempotent), or
    the DB is not configured."""


class WebhookResponse(BaseModel):
    """Response envelope for POST /v1/payments/webhook."""

    received: bool = True
    event_type: str | None = None
    report_id: str | None = None
    action: str | None = None
    """'completed', 'skipped' (already paid), 'ignored' (unhandled event type), 'error'."""
