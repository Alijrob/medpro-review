"""
app.py -- Provider Search Service FastAPI application factory (C14, Phase 2-G).

Pattern mirrors src/backend/source_health_monitor/app.py:
  - Best-effort Sentry (PII-scrubbed) and OTel instrumentation
  - Singleton OpenSearchClient + ProviderIndexer wired before first request
  - `make run-search-service` -> uvicorn backend.search_service.app:app

Non-deployed shell: no live cluster until DECISIONS.md Entry 003 (AWS
account/region) is resolved and the cluster URL is wired via
SEARCH_OPENSEARCH_URL.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from search.client import OpenSearchClient
from search.config import get_settings
from search.indexer import ProviderIndexer

from .routes import _set_singletons, router


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
        title="Provider Search Service",
        description=(
            "C14 (Phase 2-G) -- provider NPI lookup and name/specialty search "
            "over the providers-{env} OpenSearch index. "
            "Accepts CanonicalProviderProfile documents via POST /v1/providers/{npi}/index "
            "for indexing (or re-indexing) by the ingestion pipeline."
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

    # -- Wire singleton OpenSearchClient + ProviderIndexer --
    client = OpenSearchClient(settings)
    indexer = ProviderIndexer(index_name=settings.index_name)
    _set_singletons(client, indexer, settings)

    app.include_router(router)
    return app


app = create_app()
