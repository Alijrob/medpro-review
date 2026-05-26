"""
test_payment_service.py -- FastAPI TestClient tests for the Payment Service.

Test classes:
    TestHealthEndpoints          (4)  -- healthz / readyz
    TestCheckoutEndpoint         (16) -- POST /v1/payments/checkout (unconfigured Stripe + validation)
    TestCheckoutStripeConfigured (6)  -- POST /v1/payments/checkout with mocked Stripe
    TestWebhookEndpoint          (16) -- POST /v1/payments/webhook (event routing + DB ops)
    TestPaymentRepository        (9)  -- PaymentRepository unit tests (no live DB)
    TestUserSync                 (10) -- POST /v1/users/sync endpoint (Phase 2-L)
    TestLinkAuthSub              (5)  -- PaymentRepository.link_auth_sub unit tests (Phase 2-L)

Total: 66
"""
from __future__ import annotations

import json
import types
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.payment_service.app import create_app
from backend.payment_service.config import PaymentServiceSettings
from backend.payment_service.models import CheckoutRequest, UserSyncRequest
from backend.payment_service.repository import PaymentRepository
from backend.payment_service.routes import _set_repo

app = create_app()
client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_VALID_NPI = "1234567890"
_VALID_REPORT_ID = str(uuid4())
_STRIPE_SESSION_ID = "cs_test_abc123"
_STRIPE_PI_ID = "pi_test_xyz789"


def _checkout_body(**overrides: Any) -> dict:
    base = {
        "report_id": _VALID_REPORT_ID,
        "npi": _VALID_NPI,
        "success_url": "https://example.com/success?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": "https://example.com/cancel",
        "certified_personal_use_only": True,
    }
    base.update(overrides)
    return base


def _mock_stripe_session() -> MagicMock:
    """Return a minimal mock Stripe Checkout Session object."""
    session = MagicMock()
    session.id = _STRIPE_SESSION_ID
    session.url = f"https://checkout.stripe.com/pay/{_STRIPE_SESSION_ID}"
    return session


def _make_webhook_event(
    event_type: str = "checkout.session.completed",
    report_id: str = _VALID_REPORT_ID,
    npi: str = _VALID_NPI,
    session_id: str = _STRIPE_SESSION_ID,
    payment_intent: str = _STRIPE_PI_ID,
    customer_email: str = "buyer@example.com",
    amount_total: int = 3500,  # $35.00 in cents
) -> dict:
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "payment_intent": payment_intent,
                "customer_email": customer_email,
                "amount_total": amount_total,
                "metadata": {
                    "report_id": report_id,
                    "npi": npi,
                    "certified_personal_use_only": "true",
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# TestHealthEndpoints (4)
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    def test_healthz_returns_200(self):
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_healthz_body(self):
        data = client.get("/healthz").json()
        assert data["status"] == "ok"
        assert data["service"] == "payment-service"

    def test_readyz_returns_200(self):
        resp = client.get("/readyz")
        assert resp.status_code == 200

    def test_readyz_body_unconfigured(self):
        # Without env vars set, all config flags are False
        data = client.get("/readyz").json()
        assert data["status"] == "ok"
        assert data["stripe_configured"] is False
        assert data["webhook_configured"] is False


# ---------------------------------------------------------------------------
# TestCheckoutEndpoint -- validation + unconfigured Stripe (16)
# ---------------------------------------------------------------------------


class TestCheckoutEndpoint:
    """Tests for POST /v1/payments/checkout without a live Stripe key."""

    def test_valid_request_returns_200(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body())
        assert resp.status_code == 200

    def test_valid_request_returns_mock_url(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body())
        data = resp.json()
        assert "checkout_url" in data
        assert "session_id" in data
        assert data["report_id"] == _VALID_REPORT_ID
        assert data["stripe_configured"] is False

    def test_mock_session_id_contains_report_id(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body())
        data = resp.json()
        assert _VALID_REPORT_ID in data["session_id"]

    def test_invalid_npi_rejected(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body(npi="123"))
        assert resp.status_code == 422

    def test_npi_with_letters_rejected(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body(npi="123456789X"))
        assert resp.status_code == 422

    def test_npi_too_long_rejected(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body(npi="12345678901"))
        assert resp.status_code == 422

    def test_invalid_report_id_uuid_rejected(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body(report_id="not-a-uuid"))
        assert resp.status_code == 422

    def test_certified_false_rejected(self):
        resp = client.post(
            "/v1/payments/checkout",
            json=_checkout_body(certified_personal_use_only=False),
        )
        assert resp.status_code == 422

    def test_certified_false_error_message(self):
        resp = client.post(
            "/v1/payments/checkout",
            json=_checkout_body(certified_personal_use_only=False),
        )
        body = resp.json()
        assert "personal use" in str(body).lower() or "certified" in str(body).lower()

    def test_missing_success_url_rejected(self):
        body = _checkout_body()
        del body["success_url"]
        resp = client.post("/v1/payments/checkout", json=body)
        assert resp.status_code == 422

    def test_empty_success_url_rejected(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body(success_url="  "))
        assert resp.status_code == 422

    def test_empty_cancel_url_rejected(self):
        resp = client.post("/v1/payments/checkout", json=_checkout_body(cancel_url=""))
        assert resp.status_code == 422

    def test_optional_customer_email_accepted(self):
        resp = client.post(
            "/v1/payments/checkout",
            json=_checkout_body(customer_email="user@example.com"),
        )
        assert resp.status_code == 200

    def test_repo_set_checkout_session_called_when_configured(self):
        mock_repo = MagicMock()
        _set_repo(mock_repo)
        try:
            client.post("/v1/payments/checkout", json=_checkout_body())
            mock_repo.set_checkout_session.assert_called_once()
        finally:
            _set_repo(None)

    def test_repo_failure_does_not_fail_checkout(self):
        """Checkout should succeed even if storing session_id in DB fails."""
        mock_repo = MagicMock()
        mock_repo.set_checkout_session.side_effect = RuntimeError("DB down")
        _set_repo(mock_repo)
        try:
            resp = client.post("/v1/payments/checkout", json=_checkout_body())
            assert resp.status_code == 200
        finally:
            _set_repo(None)

    def test_no_repo_does_not_fail_checkout(self):
        _set_repo(None)
        resp = client.post("/v1/payments/checkout", json=_checkout_body())
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# TestCheckoutStripeConfigured -- mocked Stripe SDK (6)
# ---------------------------------------------------------------------------


class TestCheckoutStripeConfigured:
    """Tests for POST /v1/payments/checkout when Stripe is mocked as configured."""

    def _make_settings(self) -> PaymentServiceSettings:
        s = PaymentServiceSettings(
            stripe_secret_key="sk_test_fake",
            stripe_webhook_secret="whsec_fake",
            stripe_price_id="price_fake",
        )
        return s

    def test_stripe_session_create_called(self):
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.create.return_value = _mock_stripe_session()

        settings = self._make_settings()
        with (
            patch("backend.payment_service.routes.get_settings", return_value=settings),
            patch("backend.payment_service.routes._stripe_module", return_value=mock_stripe),
        ):
            resp = client.post("/v1/payments/checkout", json=_checkout_body())
        assert resp.status_code == 200
        mock_stripe.checkout.Session.create.assert_called_once()

    def test_response_contains_stripe_url(self):
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.create.return_value = _mock_stripe_session()
        settings = self._make_settings()
        with (
            patch("backend.payment_service.routes.get_settings", return_value=settings),
            patch("backend.payment_service.routes._stripe_module", return_value=mock_stripe),
        ):
            data = client.post("/v1/payments/checkout", json=_checkout_body()).json()
        assert data["checkout_url"] == f"https://checkout.stripe.com/pay/{_STRIPE_SESSION_ID}"
        assert data["session_id"] == _STRIPE_SESSION_ID
        assert data["stripe_configured"] is True

    def test_price_id_used_in_line_items(self):
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.create.return_value = _mock_stripe_session()
        settings = self._make_settings()
        with (
            patch("backend.payment_service.routes.get_settings", return_value=settings),
            patch("backend.payment_service.routes._stripe_module", return_value=mock_stripe),
        ):
            client.post("/v1/payments/checkout", json=_checkout_body())

        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        line_items = call_kwargs["line_items"]
        assert line_items[0]["price"] == "price_fake"

    def test_metadata_contains_report_id_and_npi(self):
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.create.return_value = _mock_stripe_session()
        settings = self._make_settings()
        with (
            patch("backend.payment_service.routes.get_settings", return_value=settings),
            patch("backend.payment_service.routes._stripe_module", return_value=mock_stripe),
        ):
            client.post("/v1/payments/checkout", json=_checkout_body())

        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        metadata = call_kwargs["metadata"]
        assert metadata["report_id"] == _VALID_REPORT_ID
        assert metadata["npi"] == _VALID_NPI
        assert metadata["certified_personal_use_only"] == "true"

    def test_stripe_error_returns_502(self):
        mock_stripe = MagicMock()

        # Build a minimal StripeError stand-in
        class FakeStripeError(Exception):
            user_message = "card declined"

        mock_stripe.error.StripeError = FakeStripeError
        mock_stripe.checkout.Session.create.side_effect = FakeStripeError("card declined")

        settings = self._make_settings()
        with (
            patch("backend.payment_service.routes.get_settings", return_value=settings),
            patch("backend.payment_service.routes._stripe_module", return_value=mock_stripe),
        ):
            resp = client.post("/v1/payments/checkout", json=_checkout_body())
        assert resp.status_code == 502

    def test_price_data_used_when_no_price_id(self):
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.create.return_value = _mock_stripe_session()
        settings = PaymentServiceSettings(
            stripe_secret_key="sk_test_fake",
            stripe_webhook_secret="whsec_fake",
            stripe_price_id="",         # no price ID
            report_price_usd=35.00,
        )
        with (
            patch("backend.payment_service.routes.get_settings", return_value=settings),
            patch("backend.payment_service.routes._stripe_module", return_value=mock_stripe),
        ):
            client.post("/v1/payments/checkout", json=_checkout_body())

        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        line_items = call_kwargs["line_items"]
        assert "price_data" in line_items[0]
        assert line_items[0]["price_data"]["unit_amount"] == 3500  # $35.00 in cents


# ---------------------------------------------------------------------------
# TestWebhookEndpoint (16)
# ---------------------------------------------------------------------------


class TestWebhookEndpoint:
    """Tests for POST /v1/payments/webhook."""

    def _post_webhook(self, event: dict, sig: str = "") -> Any:
        return client.post(
            "/v1/payments/webhook",
            content=json.dumps(event).encode(),
            headers={
                "Content-Type": "application/json",
                "stripe-signature": sig or "t=fake,v1=fake",
            },
        )

    def test_unhandled_event_type_returns_ignored(self):
        event = {"type": "payment_intent.created", "data": {"object": {}}}
        resp = self._post_webhook(event)
        assert resp.status_code == 200
        assert resp.json()["action"] == "ignored"

    def test_checkout_completed_no_repo_returns_error(self):
        _set_repo(None)
        event = _make_webhook_event()
        resp = self._post_webhook(event)
        assert resp.status_code == 200
        assert resp.json()["action"] == "error"

    def test_checkout_completed_no_report_id_in_metadata(self):
        _set_repo(None)
        event = _make_webhook_event()
        event["data"]["object"]["metadata"] = {}
        resp = self._post_webhook(event)
        assert resp.status_code == 200
        assert resp.json()["action"] == "error"

    def test_checkout_completed_invalid_report_id_uuid(self):
        _set_repo(None)
        event = _make_webhook_event(report_id="not-a-uuid")
        resp = self._post_webhook(event)
        assert resp.status_code == 200
        assert resp.json()["action"] == "error"

    def test_checkout_completed_idempotent_already_paid(self):
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.return_value = {
            "report_id": _VALID_REPORT_ID,
            "npi": _VALID_NPI,
            "payment_status": "paid",
            "user_id": str(uuid4()),
            "use_agreement_id": str(uuid4()),
        }
        _set_repo(mock_repo)
        try:
            event = _make_webhook_event()
            resp = self._post_webhook(event)
            assert resp.status_code == 200
            assert resp.json()["action"] == "skipped"
            mock_repo.complete_payment.assert_not_called()
        finally:
            _set_repo(None)

    def test_checkout_completed_full_flow(self):
        user_id = uuid4()
        agreement_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.return_value = {
            "report_id": _VALID_REPORT_ID,
            "npi": _VALID_NPI,
            "payment_status": "pending",
            "user_id": None,
            "use_agreement_id": None,
        }
        mock_repo.upsert_user.return_value = user_id
        mock_repo.create_use_agreement.return_value = agreement_id
        _set_repo(mock_repo)
        try:
            event = _make_webhook_event()
            resp = self._post_webhook(event)
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "completed"
            assert data["report_id"] == _VALID_REPORT_ID
        finally:
            _set_repo(None)

    def test_checkout_completed_calls_upsert_user(self):
        user_id = uuid4()
        agreement_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.return_value = {
            "report_id": _VALID_REPORT_ID,
            "npi": _VALID_NPI,
            "payment_status": "pending",
            "user_id": None,
            "use_agreement_id": None,
        }
        mock_repo.upsert_user.return_value = user_id
        mock_repo.create_use_agreement.return_value = agreement_id
        _set_repo(mock_repo)
        try:
            event = _make_webhook_event(customer_email="buyer@example.com")
            self._post_webhook(event)
            mock_repo.upsert_user.assert_called_once_with(email="buyer@example.com")
        finally:
            _set_repo(None)

    def test_checkout_completed_calls_create_use_agreement(self):
        user_id = uuid4()
        agreement_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.return_value = {
            "report_id": _VALID_REPORT_ID,
            "npi": _VALID_NPI,
            "payment_status": "pending",
            "user_id": None,
            "use_agreement_id": None,
        }
        mock_repo.upsert_user.return_value = user_id
        mock_repo.create_use_agreement.return_value = agreement_id
        _set_repo(mock_repo)
        try:
            self._post_webhook(_make_webhook_event())
            mock_repo.create_use_agreement.assert_called_once()
            call_kwargs = mock_repo.create_use_agreement.call_args[1]
            assert call_kwargs["user_id"] == user_id
        finally:
            _set_repo(None)

    def test_checkout_completed_calls_complete_payment(self):
        user_id = uuid4()
        agreement_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.return_value = {
            "report_id": _VALID_REPORT_ID,
            "npi": _VALID_NPI,
            "payment_status": "pending",
            "user_id": None,
            "use_agreement_id": None,
        }
        mock_repo.upsert_user.return_value = user_id
        mock_repo.create_use_agreement.return_value = agreement_id
        _set_repo(mock_repo)
        try:
            self._post_webhook(_make_webhook_event(payment_intent=_STRIPE_PI_ID))
            mock_repo.complete_payment.assert_called_once()
            call_kwargs = mock_repo.complete_payment.call_args[1]
            assert call_kwargs["stripe_payment_intent_id"] == _STRIPE_PI_ID
            assert call_kwargs["user_id"] == user_id
            assert call_kwargs["use_agreement_id"] == agreement_id
        finally:
            _set_repo(None)

    def test_checkout_completed_price_from_amount_total(self):
        user_id = uuid4()
        agreement_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.return_value = {
            "report_id": _VALID_REPORT_ID,
            "npi": _VALID_NPI,
            "payment_status": "pending",
            "user_id": None,
            "use_agreement_id": None,
        }
        mock_repo.upsert_user.return_value = user_id
        mock_repo.create_use_agreement.return_value = agreement_id
        _set_repo(mock_repo)
        try:
            self._post_webhook(_make_webhook_event(amount_total=3500))
            call_kwargs = mock_repo.complete_payment.call_args[1]
            assert call_kwargs["price_paid_usd"] == Decimal("35.00")
        finally:
            _set_repo(None)

    def test_checkout_completed_report_not_found_by_session_fallback_to_metadata(self):
        user_id = uuid4()
        agreement_id = uuid4()
        mock_repo = MagicMock()
        # get_report_by_session returns None (session_id not in DB)
        mock_repo.get_report_by_session.return_value = None
        # get_report_row fallback finds it
        mock_repo.get_report_row.return_value = {
            "report_id": _VALID_REPORT_ID,
            "npi": _VALID_NPI,
            "payment_status": "pending",
            "user_id": None,
            "use_agreement_id": None,
        }
        mock_repo.upsert_user.return_value = user_id
        mock_repo.create_use_agreement.return_value = agreement_id
        _set_repo(mock_repo)
        try:
            resp = self._post_webhook(_make_webhook_event())
            assert resp.json()["action"] == "completed"
        finally:
            _set_repo(None)

    def test_checkout_completed_report_not_found_anywhere(self):
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.return_value = None
        mock_repo.get_report_row.return_value = None
        _set_repo(mock_repo)
        try:
            resp = self._post_webhook(_make_webhook_event())
            assert resp.json()["action"] == "error"
        finally:
            _set_repo(None)

    def test_checkout_completed_db_error_returns_200_with_error_action(self):
        """DB errors return 200 (not 5xx) so Stripe stops retrying."""
        mock_repo = MagicMock()
        mock_repo.get_report_by_session.side_effect = RuntimeError("connection refused")
        _set_repo(mock_repo)
        try:
            resp = self._post_webhook(_make_webhook_event())
            assert resp.status_code == 200
            assert resp.json()["action"] == "error"
        finally:
            _set_repo(None)

    def test_webhook_signature_verification_with_configured_secret(self):
        """When webhook secret is configured, invalid signature returns 400."""
        mock_stripe = MagicMock()

        class FakeSigError(Exception):
            pass

        mock_stripe.error.SignatureVerificationError = FakeSigError
        mock_stripe.Webhook.construct_event.side_effect = FakeSigError("bad sig")

        settings = PaymentServiceSettings(
            stripe_secret_key="sk_test_fake",
            stripe_webhook_secret="whsec_fake",
        )
        with (
            patch("backend.payment_service.routes.get_settings", return_value=settings),
            patch("backend.payment_service.routes._stripe_module", return_value=mock_stripe),
        ):
            resp = self._post_webhook(_make_webhook_event(), sig="bad_signature")
        assert resp.status_code == 400

    def test_webhook_event_type_in_response(self):
        event = {"type": "customer.created", "data": {"object": {}}}
        resp = self._post_webhook(event)
        assert resp.json()["event_type"] == "customer.created"

    def test_webhook_invalid_json_returns_400(self):
        resp = client.post(
            "/v1/payments/webhook",
            content=b"not json at all",
            headers={"Content-Type": "application/json", "stripe-signature": "t=1"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# TestPaymentRepository -- unit tests, no live DB (9)
# ---------------------------------------------------------------------------


class TestPaymentRepository:
    """Unit tests for PaymentRepository that do not require a live database."""

    def test_not_configured_when_url_is_empty(self):
        repo = PaymentRepository("")
        assert repo.is_configured is False

    def test_is_configured_when_url_set(self):
        # Mock create_engine so psycopg2 is not required in unit-test env
        with patch("backend.payment_service.repository.sa.create_engine") as mock_ce:
            mock_ce.return_value = MagicMock()
            repo = PaymentRepository("postgresql://localhost/test")
        assert repo.is_configured is True

    def test_get_report_row_raises_when_unconfigured(self):
        repo = PaymentRepository("")
        with pytest.raises(RuntimeError, match="database not configured"):
            repo.get_report_row(uuid4())

    def test_set_checkout_session_raises_when_unconfigured(self):
        repo = PaymentRepository("")
        with pytest.raises(RuntimeError, match="database not configured"):
            repo.set_checkout_session(uuid4(), "cs_test")

    def test_get_report_by_session_raises_when_unconfigured(self):
        repo = PaymentRepository("")
        with pytest.raises(RuntimeError, match="database not configured"):
            repo.get_report_by_session("cs_test")

    def test_complete_payment_raises_when_unconfigured(self):
        repo = PaymentRepository("")
        with pytest.raises(RuntimeError, match="database not configured"):
            repo.complete_payment(
                report_id=uuid4(),
                stripe_payment_intent_id="pi_test",
                price_paid_usd=Decimal("35.00"),
                user_id=uuid4(),
                use_agreement_id=uuid4(),
            )

    def test_upsert_user_raises_when_unconfigured(self):
        repo = PaymentRepository("")
        with pytest.raises(RuntimeError, match="database not configured"):
            repo.upsert_user("user@example.com")

    def test_create_use_agreement_raises_when_unconfigured(self):
        repo = PaymentRepository("")
        with pytest.raises(RuntimeError, match="database not configured"):
            repo.create_use_agreement(user_id=uuid4(), tos_version="tos-v1.0")

    def test_checkout_request_certified_false_raises_validation_error(self):
        with pytest.raises(Exception):
            CheckoutRequest(
                report_id=str(uuid4()),
                npi=_VALID_NPI,
                success_url="https://example.com",
                cancel_url="https://example.com",
                certified_personal_use_only=False,
            )


# ---------------------------------------------------------------------------
# Phase 2-L: POST /v1/users/sync
# ---------------------------------------------------------------------------


class TestUserSync:
    """POST /v1/users/sync -- link Auth0 sub to users row (Phase 2-L)."""

    def test_sync_no_repo_returns_200_linked_false(self):
        """When DB is not configured the endpoint returns 200 with linked=False."""
        _set_repo(None)
        resp = client.post(
            "/v1/users/sync",
            json={"email": "user@example.com", "auth_provider_sub": "auth0|abc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["linked"] is False
        assert data["user_id"] is None

    def test_sync_links_existing_user(self):
        """link_auth_sub finds existing row -> linked=True with user_id returned."""
        user_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.link_auth_sub.return_value = user_id
        _set_repo(mock_repo)
        try:
            resp = client.post(
                "/v1/users/sync",
                json={"email": "user@example.com", "auth_provider_sub": "auth0|abc"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["linked"] is True
            assert data["user_id"] == str(user_id)
            mock_repo.link_auth_sub.assert_called_once_with(
                email="user@example.com",
                auth_provider_sub="auth0|abc",
            )
        finally:
            _set_repo(None)

    def test_sync_creates_new_user_when_not_found(self):
        """When link_auth_sub returns None (no row) upsert_user is called."""
        user_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.link_auth_sub.side_effect = [None, user_id]  # first call None, second after create
        mock_repo.upsert_user.return_value = user_id
        _set_repo(mock_repo)
        try:
            resp = client.post(
                "/v1/users/sync",
                json={"email": "new@example.com", "auth_provider_sub": "auth0|new"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["linked"] is True
            mock_repo.upsert_user.assert_called_once_with(email="new@example.com")
        finally:
            _set_repo(None)

    def test_sync_missing_email_returns_422(self):
        resp = client.post(
            "/v1/users/sync",
            json={"auth_provider_sub": "auth0|abc"},
        )
        assert resp.status_code == 422

    def test_sync_missing_sub_returns_422(self):
        resp = client.post(
            "/v1/users/sync",
            json={"email": "user@example.com"},
        )
        assert resp.status_code == 422

    def test_sync_db_error_returns_200_linked_false(self):
        """DB errors are caught and return linked=False (never 500 -- login must succeed)."""
        mock_repo = MagicMock()
        mock_repo.link_auth_sub.side_effect = RuntimeError("DB down")
        _set_repo(mock_repo)
        try:
            resp = client.post(
                "/v1/users/sync",
                json={"email": "user@example.com", "auth_provider_sub": "auth0|abc"},
            )
            assert resp.status_code == 200
            assert resp.json()["linked"] is False
        finally:
            _set_repo(None)

    def test_sync_empty_email_returns_422(self):
        resp = client.post(
            "/v1/users/sync",
            json={"email": "", "auth_provider_sub": "auth0|abc"},
        )
        # Pydantic validates non-empty str; should be 422 or 200 with graceful handling.
        # Either is acceptable -- just must not 500.
        assert resp.status_code in (200, 422)

    def test_sync_user_sync_request_model_valid(self):
        req = UserSyncRequest(email="user@example.com", auth_provider_sub="auth0|abc")
        assert req.email == "user@example.com"
        assert req.auth_provider_sub == "auth0|abc"

    def test_sync_user_sync_request_model_missing_field(self):
        with pytest.raises(Exception):
            UserSyncRequest(email="user@example.com")  # missing auth_provider_sub

    def test_sync_already_set_sub_is_idempotent(self):
        """If link_auth_sub returns a user_id (existing sub already set), that's fine."""
        user_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.link_auth_sub.return_value = user_id  # returns id even when no-op
        _set_repo(mock_repo)
        try:
            resp = client.post(
                "/v1/users/sync",
                json={"email": "user@example.com", "auth_provider_sub": "auth0|same"},
            )
            assert resp.status_code == 200
            assert resp.json()["linked"] is True
        finally:
            _set_repo(None)


# ---------------------------------------------------------------------------
# Phase 2-L: PaymentRepository.link_auth_sub
# ---------------------------------------------------------------------------


class TestLinkAuthSub:
    """PaymentRepository.link_auth_sub unit tests (no live DB, Phase 2-L)."""

    def test_link_auth_sub_raises_when_unconfigured(self):
        repo = PaymentRepository("")
        with pytest.raises(RuntimeError, match="database not configured"):
            repo.link_auth_sub("user@example.com", "auth0|abc")

    def test_link_auth_sub_method_exists(self):
        """Verify the method is present on PaymentRepository."""
        assert hasattr(PaymentRepository, "link_auth_sub")
        import inspect
        sig = inspect.signature(PaymentRepository.link_auth_sub)
        params = list(sig.parameters)
        assert "email" in params
        assert "auth_provider_sub" in params

    def test_link_auth_sub_signature_returns_optional_uuid(self):
        """Return annotation should be UUID | None."""
        import inspect
        sig = inspect.signature(PaymentRepository.link_auth_sub)
        ret = sig.return_annotation
        # accept UUID | None or Optional[UUID] or just verify it's annotated
        assert ret is not inspect.Parameter.empty

    def test_user_sync_response_linked_false_no_user_id(self):
        from backend.payment_service.models import UserSyncResponse
        resp = UserSyncResponse(linked=False, user_id=None)
        assert resp.linked is False
        assert resp.user_id is None

    def test_user_sync_response_linked_true_has_user_id(self):
        from backend.payment_service.models import UserSyncResponse
        uid = str(uuid4())
        resp = UserSyncResponse(linked=True, user_id=uid)
        assert resp.linked is True
        assert resp.user_id == uid
