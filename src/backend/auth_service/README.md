# Auth & Identity Service (C7) — Phase 1-F shell

FastAPI service that validates Auth0-issued JWTs and enforces the Path B
permissible-use certification at the auth layer. **Auth0 is the IDaaS**
(DECISIONS.md Entry 002) — this service never mints tokens. The dependencies here
are the reusable auth overlay that api-gateway (C8, Phase 1-G) and other services
mount.

**Status: SHELL.** Stateless except for an in-memory certification store that
stands in for the Aurora `use_agreements` table until `DATABASE_URL` is wired.
Non-deployed (no cluster yet — DECISIONS.md Entry 003).

---

## Layout

| File | Purpose |
|------|---------|
| `config.py` | `AuthSettings` (env-driven). Auth0 domain/audience/issuer, claim locations, Sentry DSN. Blank-safe. |
| `security.py` | JWKS fetch + TTL cache, RS256 verification (signature + iss + aud + exp), key-rotation retry. |
| `models.py` | `AuthenticatedUser` (from verified claims) + Path B use-agreement request/response. |
| `dependencies.py` | `get_current_user`, `require_permissions`, `require_roles`, `require_personal_use_certified`. |
| `store.py` | In-memory Path B certification store (SHELL — replaced by Aurora `use_agreements`). |
| `routes.py` | `/healthz`, `/readyz`, `/v1/me`, `/v1/use-agreement`, `/v1/reports/preflight`, `/v1/admin/ping`. |
| `app.py` | App factory: router + CORS + Sentry (SaaS, PII-scrubbed) + OTel instrumentation (best-effort). |

---

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/healthz` | none | Liveness. |
| GET | `/readyz` | none | Readiness: Auth0 configured + JWKS reachable (503 otherwise). |
| GET | `/v1/me` | bearer | The identity derived from the token. |
| POST | `/v1/use-agreement` | bearer | Record the Path B personal-use-only certification. |
| GET | `/v1/reports/preflight` | bearer + cert | Path B gate the gateway calls before accepting a report order. |
| GET | `/v1/admin/ping` | bearer + `admin` role | RBAC demo. |

---

## Token model

- Auth0 access token, **RS256**, validated against the tenant JWKS.
- Permissions: the `permissions` array (Auth0 RBAC), falling back to the `scope` string.
- Roles + email: namespaced custom claims (`https://researchyourdoctor.com/roles`,
  `.../email`) added via an Auth0 Action — OIDC forbids unnamespaced custom claims.

## Path B enforcement (DECISIONS.md Entry 004)

`POST /v1/use-agreement` requires `certified_personal_use_only: true` (400 otherwise).
`require_personal_use_certified` blocks protected actions until a certification is on
file (403). In the shell this is in-memory; the real check reads the Aurora
`use_agreements` table (the `certified_personal_use_only = true` CHECK constraint
lives in migration 0001).

---

## Run + test

```bash
make run-backend                         # uvicorn on :8000, /docs for OpenAPI
PYTHONPATH=src pytest tests/backend/ -v  # 17 behavior tests (no Auth0/network)
```

## Environment

| Variable | Purpose |
|----------|---------|
| `AUTH0_DOMAIN` | Tenant domain, e.g. `medpro.us.auth0.com`. |
| `AUTH0_AUDIENCE` | API identifier (the `aud` claim). |
| `AUTH0_ISSUER` | Optional issuer override (defaults to `https://{domain}/`). |
| `SENTRY_DSN` | Sentry SaaS DSN (blank = no-op; PII scrubbed before egress). |

In deployed environments these come from AWS Secrets Manager via External Secrets;
locally from `.env`. Blank values keep the shell importable — auth then fails closed
(401) and `/readyz` reports not-ready.
