"""
app.py -- Payment Service FastAPI application factory (Phase 2-J).

Port: 8005   (make run-payment-service)
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.payment_service.config import get_settings
from backend.payment_service.repository import PaymentRepository
from backend.payment_service.routes import _set_repo, router

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and return the FastAPI application for the Payment Service."""
    cfg = get_settings()

    app = FastAPI(
        title="Payment Service",
        description=(
            "Phase 2-J: Stripe Checkout integration for provider report purchases. "
            "Handles checkout session creation and webhook event processing."
        ),
        version="2-J",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten per-env at deploy
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Sentry (best-effort)
    # ------------------------------------------------------------------
    if cfg.sentry_dsn:
        try:
            from observability.sentry_config import init_sentry  # noqa: PLC0415
            init_sentry(cfg.sentry_dsn, service_name="payment-service")
        except Exception as exc:  # noqa: BLE001
            log.warning("Payment service: Sentry init failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # OpenTelemetry (best-effort)
    # ------------------------------------------------------------------
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: PLC0415
        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:  # noqa: BLE001
        log.debug("Payment service: OTel FastAPI instrumentation unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Startup: wire repository singleton
    # ------------------------------------------------------------------
    @app.on_event("startup")
    def _startup() -> None:
        if cfg.is_db_configured:
            try:
                repo = PaymentRepository(cfg.database_url)
                _set_repo(repo)
                log.info("Payment service: DB configured (payment_service).")
            except Exception as exc:  # noqa: BLE001
                log.warning("Payment service: DB init failed (non-fatal): %s", exc)
        else:
            log.warning(
                "Payment service: PAYMENT_DATABASE_URL not set -- "
                "checkout sessions will not be persisted."
            )

    # ------------------------------------------------------------------
    # Router
    # ------------------------------------------------------------------
    app.include_router(router)

    return app
