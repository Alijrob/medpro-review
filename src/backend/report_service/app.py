"""
app.py -- Report Service FastAPI application factory (Phase 2-I).

Phase 2-H: synchronous build from profile (no persistence).
Phase 2-I: async report request via Temporal pipeline + Aurora persistence.

Port: :8004 (run-report-service Makefile target).

Startup event wires two optional singletons:
    _repo              -- ReportRepository (requires REPORT_DATABASE_URL or DATABASE_URL)
    _temporal_client   -- temporalio.client.Client (requires REPORT_TEMPORAL_ADDRESS)

If either is unconfigured, the corresponding endpoints degrade gracefully
(persist-report returns persisted=False; request-report returns db_persisted=False /
temporal_queued=False).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router, _set_repo, _set_temporal_client

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # -- Sentry (best-effort) --
    try:
        import os
        sentry_dsn = os.environ.get("SENTRY_DSN", "")
        if sentry_dsn:
            from observability.sentry_config import init_sentry
            env = os.environ.get("ENVIRONMENT", "development")
            init_sentry(sentry_dsn, environment=env)
    except Exception:  # pragma: no cover
        pass

    # -- OpenTelemetry (best-effort) --
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument()
    except Exception:  # pragma: no cover
        pass

    app = FastAPI(
        title="Report Service",
        description=(
            "C17 + C18 -- builds ProviderReport objects from CanonicalProviderProfile "
            "(synchronous Phase 2-H) and triggers the full Temporal pipeline via "
            "POST /v1/reports/request (async Phase 2-I)."
        ),
        version="0.2.0",
    )

    # -- CORS --
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(router)

    # -- Startup: wire optional singletons --
    @app.on_event("startup")  # type: ignore[misc]
    async def _startup() -> None:
        from .config import get_settings  # noqa: PLC0415
        settings = get_settings()

        # ReportRepository
        if settings.is_db_configured:
            try:
                from .repository import ReportRepository  # noqa: PLC0415
                _set_repo(ReportRepository(settings.database_url))
                log.info("ReportRepository initialised (DB configured).")
            except Exception as exc:  # pragma: no cover  # noqa: BLE001
                log.warning("ReportRepository init failed: %s", exc)
        else:
            log.info("REPORT_DATABASE_URL not set -- report persistence disabled.")

        # Temporal client
        if settings.is_temporal_configured:
            try:
                import temporalio.client  # noqa: PLC0415
                client = await temporalio.client.Client.connect(
                    settings.temporal_address,
                    namespace=settings.temporal_namespace,
                )
                _set_temporal_client(client)
                log.info(
                    "Temporal client connected: address=%s namespace=%s",
                    settings.temporal_address,
                    settings.temporal_namespace,
                )
            except Exception as exc:  # pragma: no cover  # noqa: BLE001
                log.warning("Temporal client init failed: %s", exc)
        else:
            log.info("REPORT_TEMPORAL_ADDRESS not set -- Temporal pipeline disabled.")

    return app


# Module-level app instance for uvicorn / Makefile
app = create_app()
