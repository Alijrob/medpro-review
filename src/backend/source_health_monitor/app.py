"""
app.py — Source Health Monitor FastAPI application factory (C24).

Pattern mirrors auth_service, api_gateway, and audit_service:
  - Best-effort Sentry (PII-scrubbed via 1-D sentry_config) and OTel
  - Singleton HealthStore + SourceHealthMonitor wired before first request
  - `make run-monitor` -> uvicorn backend.source_health_monitor.app:app

Non-deployed shell: no cluster, no Aurora. All state is in-memory until
Entry 003 (AWS account/region) is resolved and the DB URL is wired.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .monitor import SourceHealthMonitor
from .routes import _set_singletons, router
from .store import HealthStore


def create_app() -> FastAPI:
    settings = get_settings()

    # -- Sentry (best-effort; PII scrubbed before egress -- 1-D sentry_config) --
    if settings.sentry_dsn:
        try:
            from observability.sentry_config import init_sentry

            init_sentry(settings.sentry_dsn, environment=settings.environment)
        except Exception:  # pragma: no cover
            pass

    # -- OpenTelemetry FastAPI instrumentation (best-effort) --
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
    except Exception:  # pragma: no cover
        pass

    app = FastAPI(
        title="Source Health Monitor",
        description=(
            "C24 — monitors availability, schema drift, and stale-source state "
            "for all P1 federal data sources."
        ),
        version="0.1.0",
    )

    # -- CORS --
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # -- Wire singleton HealthStore + SourceHealthMonitor --
    store = HealthStore(history_limit=settings.history_limit)
    monitor = SourceHealthMonitor(
        failure_warning_threshold=settings.failure_warning_threshold,
        failure_critical_threshold=settings.failure_critical_threshold,
        stale_bulk_hours=settings.stale_bulk_hours,
        stale_api_hours=settings.stale_api_hours,
    )
    _set_singletons(store, monitor)

    app.include_router(router)
    return app


app = create_app()
