"""
routes.py -- Payment Service API routes (Phase 2-J).

Endpoints:

    GET  /healthz                       -- liveness
    GET  /readyz                        -- readiness (Stripe + DB config check)

    POST /v1/payments/checkout          -- create Stripe Checkout session for a report purchase
    POST /v1/payments/webhook           -- Stripe webhook receiver (checkout.session.completed)

POST /v1/payments/checkout
    Requires a reports row to exist (created by POST /v1/reports/request).
    Validates NPI format and certified_personal_use_only=True.
    Creates a Stripe Checkout Session with metadata {report_id, npi, certified=true}.
    Stores stripe_checkout_session_id on the reports row, advances payment_status='pending'.
    Returns {checkout_url, session_id, report_id}.

    When Stripe is not configured (PAYMENT_STRIPE_SECRET_KEY not set):
    Returns a mock checkout_url so local dev / CI can test the surrounding flow
    without a live Stripe key.  stripe_configured=False in response.

POST /v1/payments/webhook
    Raw request body required -- do NOT parse as JSON before Stripe signature check.
    Verifies Stripe-Signature header with PAYMENT_STRIPE_WEBHOOK_SECRET.
    Routes checkout.session.completed:
      1. Looks up report by stripe_checkout_session_id (from session metadata).
      2. Idempotency: if payment_status already 'paid', returns 200 (action='skipped').
      3. Upserts user row by customer_email.
      4. Creates use_agreements row (certified_personal_use_only=True).
      5. Calls complete_payment to backfill user_id, use_agreement_id,
         stripe_payment_intent_id, price_paid_usd on the reports row.
    Other event types return 200 with action='ignored'.
    Returns 400 on signature verification failure (Stripe retries; permanent errors =  400).

Singleton injection:
    _set_repo(repo)          -- injected by app.py startup event
    Both default to None (test-safe; unconfigured = graceful degradation).
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from backend.payment_service.config import get_settings
from backend.payment_service.models import CheckoutRequest, CheckoutResponse, WebhookResponse

router = APIRouter()
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton reference (set by app factory; None = not configured)
# ---------------------------------------------------------------------------

_repo = None   # PaymentRepository | None


def _set_repo(repo: Any) -> None:
    global _repo
    _repo = repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NPI_RE = re.compile(r"^\d{10}$")


def _stripe_module() -> Any:
    """
    Lazy import of the stripe SDK.  Returns the module or None if not installed.
    This allows the service to start (with degraded functionality) even if
    stripe is not yet installed in the local dev environment.
    """
    try:
        import stripe  # noqa: PLC0415
        return stripe
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


@router.get("/healthz", tags=["health"])
def healthz() -> dict:
    return {"status": "ok", "service": "payment-service"}


@router.get("/readyz", tags=["health"])
def readyz() -> dict:
    cfg = get_settings()
    return {
        "status": "ok",
        "service": "payment-service",
        "stripe_configured": cfg.is_stripe_configured,
        "webhook_configured": cfg.is_webhook_configured,
        "db_configured": cfg.is_db_configured,
    }


# ---------------------------------------------------------------------------
# POST /v1/payments/checkout
# ---------------------------------------------------------------------------


@router.post(
    "/v1/payments/checkout",
    response_model=CheckoutResponse,
    status_code=200,
    tags=["payments"],
    summary="Create a Stripe Checkout session to purchase an NPI provider report",
    description=(
        "Phase 2-J: validates NPI + certified_personal_use_only, creates a Stripe Checkout "
        "session, stores the session ID on the reports row, and returns {checkout_url, session_id}."
    ),
)
def create_checkout_session(body: CheckoutRequest) -> CheckoutResponse:
    """
    Create a Stripe Checkout Session for purchasing a provider report.

    certified_personal_use_only must be True (Path B gate).
    The Pydantic model validator enforces this.
    """
    cfg = get_settings()

    # Validate NPI
    if not _NPI_RE.match(body.npi):
        raise HTTPException(
            status_code=422,
            detail="NPI must be exactly 10 digits (numeric).",
        )

    # Validate report_id UUID format
    try:
        report_uuid = UUID(body.report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid report_id: must be a UUID. Got: {body.report_id!r}",
        ) from exc

    # Validate URLs are non-empty
    if not body.success_url.strip() or not body.cancel_url.strip():
        raise HTTPException(
            status_code=422,
            detail="success_url and cancel_url must be non-empty strings.",
        )

    # -----------------------------------------------------------------
    # Stripe session creation
    # -----------------------------------------------------------------
    stripe = _stripe_module()

    if cfg.is_stripe_configured and stripe is not None:
        stripe.api_key = cfg.stripe_secret_key

        # Build line_items: prefer Price ID if configured, else use price_data
        if cfg.stripe_price_id:
            line_items = [{"price": cfg.stripe_price_id, "quantity": 1}]
        else:
            line_items = [
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(cfg.report_price_usd * 100),  # cents
                        "product_data": {
                            "name": "Provider Intelligence Report",
                            "description": (
                                f"Comprehensive background report for NPI {body.npi}. "
                                "For personal use only."
                            ),
                        },
                    },
                    "quantity": 1,
                }
            ]

        session_params: dict[str, Any] = {
            "mode": "payment",
            "line_items": line_items,
            "success_url": body.success_url,
            "cancel_url": body.cancel_url,
            "metadata": {
                "report_id": body.report_id,
                "npi": body.npi,
                "certified_personal_use_only": "true",
            },
        }
        if body.customer_email:
            session_params["customer_email"] = body.customer_email

        try:
            session = stripe.checkout.Session.create(**session_params)
        except stripe.error.StripeError as exc:
            log.error("Stripe session creation failed: %s", exc)
            raise HTTPException(
                status_code=502,
                detail=f"Stripe error: {exc.user_message or str(exc)}",
            ) from exc

        session_id: str = session.id
        checkout_url: str = session.url
        stripe_configured = True
    else:
        # Not configured -- return a mock response for dev / CI
        session_id = f"cs_test_mock_{body.report_id}"
        checkout_url = f"https://checkout.stripe.com/mock?session_id={session_id}"
        stripe_configured = False
        log.warning(
            "Payment service: Stripe not configured -- returning mock checkout URL for report_id=%s",
            body.report_id,
        )

    # -----------------------------------------------------------------
    # Persist the session ID on the report row
    # -----------------------------------------------------------------
    if _repo is not None:
        try:
            _repo.set_checkout_session(report_uuid, session_id)
        except Exception as exc:  # noqa: BLE001
            # Non-fatal: log and continue. The session was created; losing the DB link
            # is recoverable via the session metadata in the webhook.
            log.warning(
                "Payment: could not store session_id in reports table: %s", exc
            )

    return CheckoutResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        report_id=body.report_id,
        stripe_configured=stripe_configured,
    )


# ---------------------------------------------------------------------------
# POST /v1/payments/webhook
# ---------------------------------------------------------------------------


@router.post(
    "/v1/payments/webhook",
    response_model=WebhookResponse,
    status_code=200,
    tags=["payments"],
    summary="Stripe webhook receiver",
    description=(
        "Phase 2-J: receives Stripe events, verifies the Stripe-Signature header, "
        "and processes checkout.session.completed events."
    ),
)
async def stripe_webhook(request: Request) -> WebhookResponse:
    """
    Stripe sends this endpoint a raw POST with a JSON body and a Stripe-Signature header.

    We MUST read the raw bytes (not the parsed JSON) for signature verification.
    """
    cfg = get_settings()
    stripe = _stripe_module()

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # -----------------------------------------------------------------
    # Signature verification
    # -----------------------------------------------------------------
    if cfg.is_webhook_configured and stripe is not None:
        stripe.api_key = cfg.stripe_secret_key
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, cfg.stripe_webhook_secret
            )
        except stripe.error.SignatureVerificationError as exc:
            log.warning("Stripe webhook signature verification failed: %s", exc)
            raise HTTPException(
                status_code=400,
                detail="Invalid Stripe webhook signature.",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            log.error("Stripe webhook event construction error: %s", exc)
            raise HTTPException(
                status_code=400,
                detail=f"Webhook error: {exc}",
            ) from exc
    else:
        # Webhook secret not configured -- accept but log a warning.
        # This path is intentional for dev/CI where Stripe is mocked.
        import json as _json  # noqa: PLC0415
        log.warning("Payment service: webhook secret not configured -- skipping signature check.")
        try:
            event = _json.loads(payload)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

    event_type: str = event["type"] if isinstance(event, dict) else event.type

    # -----------------------------------------------------------------
    # Route event types
    # -----------------------------------------------------------------
    if event_type == "checkout.session.completed":
        return await _handle_checkout_completed(event, cfg)

    # Unhandled event -- acknowledge receipt so Stripe stops retrying
    log.debug("Stripe webhook: ignoring event type=%s", event_type)
    return WebhookResponse(event_type=event_type, action="ignored")


async def _handle_checkout_completed(event: Any, cfg: Any) -> WebhookResponse:
    """
    Process a checkout.session.completed event.

    Steps:
      1. Extract report_id from session metadata.
      2. Look up the report row (by session_id from the event object).
      3. Idempotency guard: if payment_status == 'paid', skip.
      4. Upsert user by customer_email.
      5. Create use_agreements row.
      6. complete_payment: backfill user_id, use_agreement_id, stripe_payment_intent_id.
    """
    # Extract session object (handle both stripe SDK object and plain dict)
    if isinstance(event, dict):
        session = event.get("data", {}).get("object", {})
    else:
        session = event.data.object

    # Resolve session fields (SDK object or dict)
    def _get(obj: Any, key: str) -> Any:
        return obj[key] if isinstance(obj, dict) else getattr(obj, key, None)

    session_id: str = _get(session, "id") or ""
    payment_intent_id: str = _get(session, "payment_intent") or ""
    customer_email: str = _get(session, "customer_email") or _get(session, "customer_details") or ""
    amount_total: int | None = _get(session, "amount_total")

    # customer_email may be nested in customer_details (Stripe SDK dict)
    if isinstance(customer_email, dict):
        customer_email = customer_email.get("email") or ""

    # Extract metadata
    metadata: dict = _get(session, "metadata") or {}
    if not isinstance(metadata, dict):
        metadata = dict(metadata)

    report_id_str: str = metadata.get("report_id", "")
    npi: str = metadata.get("npi", "")

    if not report_id_str:
        log.warning(
            "Stripe webhook: checkout.session.completed missing report_id in metadata. "
            "session_id=%s", session_id
        )
        return WebhookResponse(
            event_type="checkout.session.completed",
            action="error",
            report_id=None,
        )

    try:
        report_uuid = UUID(report_id_str)
    except ValueError:
        log.error("Stripe webhook: invalid report_id UUID in metadata: %r", report_id_str)
        return WebhookResponse(
            event_type="checkout.session.completed",
            action="error",
            report_id=report_id_str,
        )

    price_paid = Decimal(str(amount_total / 100)) if amount_total else Decimal(str(cfg.report_price_usd))

    # -----------------------------------------------------------------
    # DB operations
    # -----------------------------------------------------------------
    if _repo is None:
        log.warning(
            "Stripe webhook: DB not configured -- cannot record payment. "
            "report_id=%s session_id=%s", report_id_str, session_id
        )
        return WebhookResponse(
            event_type="checkout.session.completed",
            action="error",
            report_id=report_id_str,
        )

    try:
        # 1. Look up report row (by session_id for speed; fall back to report_id from metadata)
        report_row: dict | None = None
        if session_id:
            report_row = _repo.get_report_by_session(session_id)
        if report_row is None:
            report_row = _repo.get_report_row(report_uuid)

        if report_row is None:
            log.error(
                "Stripe webhook: report not found. report_id=%s session_id=%s",
                report_id_str, session_id,
            )
            return WebhookResponse(
                event_type="checkout.session.completed",
                action="error",
                report_id=report_id_str,
            )

        # 2. Idempotency guard
        if report_row.get("payment_status") == "paid":
            log.info(
                "Stripe webhook: report already paid (idempotent). report_id=%s", report_id_str
            )
            return WebhookResponse(
                event_type="checkout.session.completed",
                action="skipped",
                report_id=report_id_str,
            )

        # 3. Upsert user
        email_to_use = customer_email or f"unknown-{report_id_str}@stripe.placeholder"
        user_id: UUID = _repo.upsert_user(email=email_to_use)

        # 4. Create use_agreements row
        # ip_address: Stripe webhook IPs are known ranges; we record the forwarded-for if present.
        # (In practice Stripe webhooks have no user IP -- we record None.)
        agreement_id: UUID = _repo.create_use_agreement(
            user_id=user_id,
            tos_version=cfg.tos_version,
            ip_address=None,
            user_agent="Stripe/1.0 (webhook)",
        )

        # 5. complete_payment
        _repo.complete_payment(
            report_id=report_uuid,
            stripe_payment_intent_id=payment_intent_id,
            price_paid_usd=price_paid,
            user_id=user_id,
            use_agreement_id=agreement_id,
        )

        log.info(
            "Stripe webhook: payment completed. report_id=%s user_id=%s pi=%s",
            report_id_str, user_id, payment_intent_id,
        )
        return WebhookResponse(
            event_type="checkout.session.completed",
            action="completed",
            report_id=report_id_str,
        )

    except Exception as exc:  # noqa: BLE001
        log.error(
            "Stripe webhook: DB error processing checkout.session.completed: %s", exc,
            exc_info=True,
        )
        # Return 200 to prevent Stripe from retrying a fundamentally broken DB state.
        # The event should be re-processed by an ops engineer via the Stripe dashboard.
        return WebhookResponse(
            event_type="checkout.session.completed",
            action="error",
            report_id=report_id_str,
        )
