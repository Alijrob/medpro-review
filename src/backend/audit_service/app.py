"""
app.py — FastAPI application factory for the audit ledger service (C5-audit).

Mirrors the auth service factory: router + CORS + Sentry (SaaS, PII scrubbed by the
1-D sentry_config) + OpenTelemetry instrumentation. Sentry and OTel are best-effort —
a missing optional dependency or unset DSN must never stop the service from booting.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import get_settings
from .routes import router

logger = logging.getLogger("audit_service")


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
        title="medpro-review Audit Ledger Service",
        version="0.1.0",
        description="Append-only, hash-chained audit ledger (C5-audit, Phase 1-I shell).",
    )

    if settings.cors_allow_origins:
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
