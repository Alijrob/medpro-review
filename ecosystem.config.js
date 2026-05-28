// ecosystem.config.js -- PM2 process definitions for medpro-review (Phase 6-B)
//
// Usage:
//   bash scripts/pm2-start.sh start     # recommended: loads .env.hostinger, builds frontend, starts all
//   bash scripts/pm2-start.sh restart   # reload env + restart all processes
//   bash scripts/pm2-start.sh stop
//   bash scripts/pm2-start.sh status
//
// Or manually:
//   source .env.hostinger && pm2 start ecosystem.config.js
//
// Processes:
//   medpro-auth       :8000  Auth0 JWT validation (auth-service)
//   medpro-gateway    :8080  Rate-limit / idempotency / OPA hook (api-gateway)
//   medpro-audit      :8001  Append-only audit ledger (audit-service)
//   medpro-monitor    :8002  Source health dashboard (source-health-monitor)
//   medpro-search     :8003  Provider NPI / name search (search-service, OpenSearch)
//   medpro-reports    :8004  Report pipeline trigger + status poll (report-service)
//   medpro-payments   :8005  Stripe checkout + webhook (payment-service)
//   medpro-frontend   :3100  Next.js App Router
//
// Temporal worker is NOT included in Phase 6-B.
// Install Temporal server on Hostinger before enabling the worker process.

'use strict';

const ROOT  = '/root/medpro-review';
const SRC   = ROOT + '/src';

// Absolute path to the Poetry binary installed by Poetry's own installer.
// Override with POETRY_BIN env var if installed elsewhere.
const POETRY = process.env.POETRY_BIN || '/root/.local/bin/poetry';

// ---------------------------------------------------------------------------
// Shared environment injected into every Python/uvicorn process.
// Values are read from the shell environment (sourced from .env.hostinger).
// ---------------------------------------------------------------------------
const sharedPyEnv = {
  PYTHONPATH:         SRC,
  ENVIRONMENT:        'production',

  // Shared DB + cache URLs (used as fallback by services that don't set their own prefix)
  DATABASE_URL:       process.env.DATABASE_URL       || '',
  AUDIT_DATABASE_URL: process.env.AUDIT_DATABASE_URL || '',
  REDIS_URL:          process.env.REDIS_URL          || '',

  // Auth0 -- consumed by auth-service (no prefix) and api-gateway (reuses auth overlay)
  AUTH0_DOMAIN:       process.env.AUTH0_DOMAIN       || '',
  AUTH0_AUDIENCE:     process.env.AUTH0_AUDIENCE     || '',
  AUTH0_ISSUER:       process.env.AUTH0_ISSUER       || '',

  // CORS -- researchyourdoctor.com only in production
  CORS_ALLOW_ORIGINS: '["https://researchyourdoctor.com"]',

  // Sentry SaaS (Phase 1-D, Entry 009) -- blank disables it cleanly
  SENTRY_DSN:         process.env.SENTRY_DSN         || '',
};

// Common PM2 process defaults for all apps
const defaults = {
  cwd:                ROOT,
  autorestart:        true,
  watch:              false,
  max_restarts:       10,
  restart_delay:      5000,      // 5 s back-off between crash-restarts
  max_memory_restart: '350M',    // guard against runaway memory; tune up if needed
  log_date_format:    'YYYY-MM-DD HH:mm:ss Z',
};

// Build a uvicorn process entry.
// module  -- Python module path, e.g. "backend.auth_service.app:app"
// port    -- TCP port the service listens on
// extraEnv -- service-specific env vars merged on top of sharedPyEnv
function uvicorn(name, module, port, extraEnv) {
  return Object.assign({}, defaults, {
    name,
    script:      POETRY,
    args:        'run uvicorn ' + module + ' --host 0.0.0.0 --port ' + port + ' --workers 1',
    interpreter: 'none',        // exec Poetry directly; PM2 tracks its PID
    env:         Object.assign({}, sharedPyEnv, extraEnv || {}),
  });
}

module.exports = {
  apps: [
    // -----------------------------------------------------------------------
    // auth-service :8000
    // JWT validation via Auth0 JWKS. Boots safely with blank Auth0 vars --
    // /readyz reports not-ready until AUTH0_DOMAIN + AUTH0_AUDIENCE are set.
    // -----------------------------------------------------------------------
    uvicorn('medpro-auth', 'backend.auth_service.app:app', 8000),

    // -----------------------------------------------------------------------
    // api-gateway :8080
    // Rate-limit + idempotency (Redis-backed when REDIS_URL is set), OPA hook
    // (OPA_ENABLED=false by default -- no sidecar on Hostinger).
    // -----------------------------------------------------------------------
    uvicorn('medpro-gateway', 'backend.api_gateway.app:app', 8080),

    // -----------------------------------------------------------------------
    // audit-service :8001
    // Append-only, hash-chained audit ledger. In-memory shell until
    // AUDIT_DATABASE_URL is wired; chain is not persisted without it.
    // -----------------------------------------------------------------------
    uvicorn('medpro-audit', 'backend.audit_service.app:app', 8001),

    // -----------------------------------------------------------------------
    // source-health-monitor :8002
    // Tracks adapter health + alerts. In-memory shell until DATABASE_URL set.
    // -----------------------------------------------------------------------
    uvicorn('medpro-monitor', 'backend.source_health_monitor.app:app', 8002),

    // -----------------------------------------------------------------------
    // search-service :8003
    // Provider NPI / name search via OpenSearch. /readyz reports not-ready
    // until SEARCH_OPENSEARCH_URL points at a live cluster.
    // OpenSearch is not installed on Hostinger for Phase 6-B validation --
    // the service starts and returns 503 on search endpoints until it is.
    // -----------------------------------------------------------------------
    uvicorn('medpro-search', 'backend.search_service.app:app', 8003, {
      SEARCH_OPENSEARCH_URL:      process.env.SEARCH_OPENSEARCH_URL      || 'http://127.0.0.1:9200',
      SEARCH_OPENSEARCH_PASSWORD: process.env.SEARCH_OPENSEARCH_PASSWORD || '',
      SEARCH_INDEX_NAME:          process.env.SEARCH_INDEX_NAME          || 'providers-prod',
    }),

    // -----------------------------------------------------------------------
    // report-service :8004
    // Accepts report requests, fires Temporal workflow, polls status.
    // REPORT_TEMPORAL_ADDRESS defaults to localhost:7233 -- workflows will fail
    // to dispatch until Temporal server is installed (post Phase 6-B).
    // REPORT_DATABASE_URL is set here so pydantic's REPORT_ prefix picks it up.
    // -----------------------------------------------------------------------
    uvicorn('medpro-reports', 'backend.report_service.app:app', 8004, {
      REPORT_DATABASE_URL:     process.env.DATABASE_URL            || '',
      REPORT_TEMPORAL_ADDRESS: process.env.REPORT_TEMPORAL_ADDRESS || 'localhost:7233',
    }),

    // -----------------------------------------------------------------------
    // payment-service :8005
    // Stripe Checkout session creation + webhook handler.
    // Boots safely with blank Stripe keys -- /readyz reports not-ready.
    // PAYMENT_DATABASE_URL is set here so pydantic's PAYMENT_ prefix picks it up.
    // -----------------------------------------------------------------------
    uvicorn('medpro-payments', 'backend.payment_service.app:app', 8005, {
      PAYMENT_DATABASE_URL:          process.env.DATABASE_URL                  || '',
      PAYMENT_STRIPE_SECRET_KEY:     process.env.PAYMENT_STRIPE_SECRET_KEY     || '',
      PAYMENT_STRIPE_WEBHOOK_SECRET: process.env.PAYMENT_STRIPE_WEBHOOK_SECRET || '',
      PAYMENT_STRIPE_PRICE_ID:       process.env.PAYMENT_STRIPE_PRICE_ID       || '',
    }),

    // -----------------------------------------------------------------------
    // frontend :3100
    // Next.js App Router (Auth0, TanStack Query, Stripe redirect).
    // Run `npm run build` inside src/frontend before starting (pm2-start.sh
    // does this automatically on first start).
    // -----------------------------------------------------------------------
    Object.assign({}, defaults, {
      name:               'medpro-frontend',
      script:             'npm',
      args:               'run start',
      cwd:                ROOT + '/src/frontend',
      interpreter:        'none',
      max_memory_restart: '512M',
      env: {
        NODE_ENV:              'production',
        PORT:                  '3100',
        // Auth0 SDK (server-side)
        AUTH0_SECRET:          process.env.AUTH0_SECRET          || '',
        AUTH0_BASE_URL:        process.env.AUTH0_BASE_URL        || 'https://researchyourdoctor.com',
        AUTH0_ISSUER_BASE_URL: process.env.AUTH0_ISSUER_BASE_URL || '',
        AUTH0_CLIENT_ID:       process.env.AUTH0_CLIENT_ID       || '',
        AUTH0_CLIENT_SECRET:   process.env.AUTH0_CLIENT_SECRET   || '',
        AUTH0_AUDIENCE:        process.env.AUTH0_AUDIENCE        || '',
        // Public URL (baked into the browser bundle at build time -- rebuild if changed)
        NEXT_PUBLIC_APP_URL:   'https://researchyourdoctor.com',
        // Backend proxies -- frontend API routes forward to these; never exposed to browser
        SEARCH_SERVICE_URL:    'http://127.0.0.1:8003',
        REPORT_SERVICE_URL:    'http://127.0.0.1:8004',
        PAYMENT_SERVICE_URL:   'http://127.0.0.1:8005',
      },
    }),
  ],
};
