# API Gateway (C8) — Phase 1-G shell (+ 1-H OPA baseline)

The single ingress for the platform API. Mounts the Phase 1-F auth overlay and
adds the cross-cutting concerns every downstream service relies on. Non-deployed
shell; runnable locally. Phase 1-H adds the OPA sidecar that backs the authz hook
and the NetworkPolicy baseline for the namespace.

---

## What it does

| Concern | Where | Shell behavior |
|---------|-------|----------------|
| AuthN | reuses `backend.auth_service.dependencies` | Auth0 JWT validation (RS256/JWKS) |
| AuthZ | `opa.py` — `require_authz(action, resource)` | queries the OPA sidecar; fail closed (Phase 1-H: enabled in-cluster, off locally) |
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

### OPA sidecar + network baseline (Phase 1-H, DECISIONS.md Entry 012)

The pod carries an **OPA sidecar** (`openpolicyagent/opa:0.70.0-rootless`) that loads
the policy bundle (`src/policy`) from the `opa-policy` ConfigMap mounted at `/policy`.
Its decision API binds to `127.0.0.1:8181` (same-pod only); health + metrics are on the
diagnostic port `8282`. The gateway container sets `OPA_ENABLED=true` and
`OPA_URL=http://127.0.0.1:8181`, switching on the already-wired fail-closed `require_authz`
hook in-cluster (local dev stays off — no sidecar). The ConfigMap is delivered ahead of the
pod by the `opa-policy` ArgoCD app (sync-wave -1).

`deploy/networkpolicies.yaml` adds the zero-trust baseline for the namespace: default-deny
ingress+egress, then allow DNS, API ingress from the ingress tier + metrics scrape from
`observability`, and egress to `identity`/`reports`/`workers` (Entry 011 cross-namespace
paths), the OTel gateway, and external HTTPS:443 (Auth0 JWKS).

---

## Run + test

```bash
make run-gateway                                 # uvicorn on :8080, /docs
PYTHONPATH=src pytest tests/backend/test_api_gateway.py -v   # 15 behavior tests
make opa-test                                    # OPA bundle: opa check + 16 unit tests
kustomize build src/backend/api_gateway/deploy   # Deployment (incl. opa sidecar) + Service + NetworkPolicies
kustomize build src/policy                       # opa-policy ConfigMap
```
