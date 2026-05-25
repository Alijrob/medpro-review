"""
app.py — FastAPI application factory for the API gateway.

Middleware order (outermost first on request): CORS, SecurityHeaders, RequestID,
RateLimit, Idempotency, then the route. Sentry (SaaS, PII-scrubbed) and OTel
instrumentation are best-effort and never fatal.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import get_settings
from .middleware import (
    IdempotencyMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from .routes import router

logger = logging.getLogger("api_gateway")


def _init_sentry(service_name: str) -> None:
    try:
        from observability.sentry.sentry_config import init_sentry

        init_sentry(service_name)  # no-op when SENTRY_DSN unset
    except Exception as exc:
        logger.warning("sentry init skipped: %s", exc)


def _instrument_otel(app: FastAPI) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("otel instrumentation skipped: %s", exc)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="medpro-review API Gateway",
        version="0.1.0",
        description="API gateway (C8, Phase 1-G shell): auth overlay + rate limit + idempotency + OPA hook.",
    )

    # Innermost first; each add_middleware wraps the previous, so the LAST added is
    # the outermost. Add inner-to-outer for the documented order.
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    try:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("CORS middleware skipped: %s", exc)

    _init_sentry(settings.service_name)
    _instrument_otel(app)

    app.include_router(router)
    return app


app = create_app()
