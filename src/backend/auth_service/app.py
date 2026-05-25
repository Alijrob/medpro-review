"""
app.py — FastAPI application factory for the auth service.

Wires the router, CORS, Sentry (SaaS, DECISIONS.md Entry 009 — PII scrubbed in
sentry_config before egress), and OpenTelemetry FastAPI instrumentation. Sentry
and OTel are best-effort: a missing optional dependency or unset DSN must never
stop the service from booting (they no-op).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import get_settings
from .routes import router

logger = logging.getLogger("auth_service")


def _init_sentry(service_name: str) -> None:
    try:
        from observability.sentry.sentry_config import init_sentry

        init_sentry(service_name)  # no-op when SENTRY_DSN is unset
    except Exception as exc:  # optional dep / no DSN — never fatal
        logger.warning("sentry init skipped: %s", exc)


def _instrument_otel(app: FastAPI) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:  # optional dep / no collector — never fatal
        logger.warning("otel instrumentation skipped: %s", exc)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="medpro-review Auth & Identity Service",
        version="0.1.0",
        description="Auth0 JWT validation + Path B permissible-use enforcement (C7, Phase 1-F shell).",
    )

    # CORS — the Next.js frontend origin. Tightened per environment in Phase 2-K.
    try:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("CORS middleware skipped: %s", exc)

    _init_sentry(settings.service_name)
    _instrument_otel(app)

    app.include_router(router)
    return app


app = create_app()
