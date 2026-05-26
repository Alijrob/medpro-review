"""
app.py -- Report Service FastAPI application factory (C17 basic, Phase 2-H).

Non-deployed shell. Returns JSON reports and HTML reports from pre-built
CanonicalProviderProfile objects. Live pipeline integration (Temporal start)
is wired in Phase 2-I+.

Port: :8004 (run-report-service Makefile target).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router


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
            "C17 (basic) -- builds ProviderReport objects from CanonicalProviderProfile "
            "and serves them as JSON or HTML. "
            "Full Temporal pipeline integration is Phase 2-I+."
        ),
        version="0.1.0",
    )

    # -- CORS --
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


# Module-level app instance for uvicorn / Makefile
app = create_app()
