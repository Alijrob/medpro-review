# API Gateway (C8) — Phase 1-G shell

The single ingress for the platform API. Mounts the Phase 1-F auth overlay and
adds the cross-cutting concerns every downstream service relies on. Non-deployed
shell; runnable locally.

---

## What it does

| Concern | Where | Shell behavior |
|---------|-------|----------------|
| AuthN | reuses `backend.auth_service.dependencies` | Auth0 JWT validation (RS256/JWKS) |
| AuthZ | `opa.py` — `require_authz(action, resource)` | OPA off → allow authenticated; on → fail closed |
| Path B | reuses `require_personal_use_certified` | blocks report orders until certified (Entry 004) |
| Rate limit | `middleware.RateLimitMiddleware` | in-memory fixed window → 429 + Retry-After |
| Idempotency | `middleware.IdempotencyMiddleware` | in-memory replay of 2xx by `Idempotency-Key` |
| Request ID | `middleware.RequestIDMiddleware` | propagate/generate `X-Request-ID` |
| Hardening | `middleware.SecurityHeadersMiddleware` | nosniff, DENY, HSTS, no-referrer |

In-memory stores (`stores.py`) are swapped for Redis when `REDIS_URL` is set.

---

## Endpoints

| Method | Path | Guard | Purpose |
|--------|------|-------|---------|
| GET | `/healthz` | none | Liveness. |
| GET | `/readyz` | none | Ready unless OPA enabled+unreachable. |
| GET | `/v1/whoami` | auth | Proves the auth overlay is mounted. |
| POST | `/v1/reports` | auth + Path B + OPA + idempotent | Stub for the C17 report service — exercises the full chain. |

---

## Topology

Runs in the **`api-gateway`** namespace with service account **`api-gateway-sa`**
(IRSA from the 1-B iam module; DECISIONS.md Entry 011). The Phase 1-D ServiceMonitor
scrapes the `metrics` port. Deployed by the `api-gateway` ArgoCD Application
(`src/gitops/argocd/workloads/api-gateway.yaml`, `workloads` project) from the
kustomize bundle in `deploy/`. Image + ECR registry are PLACEHOLDER until built and
Entry 003 resolves; the deploy guard blocks sync until then.

---

## Run + test

```bash
make run-gateway                                 # uvicorn on :8080, /docs
PYTHONPATH=src pytest tests/backend/test_api_gateway.py -v   # 15 behavior tests
```
