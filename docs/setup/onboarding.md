# Onboarding — Medical Professionals Review

**Project:** Healthcare Provider Intelligence & Vetting Platform
**Product:** Medical Professionals Review
**Domain:** researchyourdoctor.com
**Owner:** PAGIOS / Alijrob

---

## What This Project Does

A consumer-facing service that generates comprehensive intelligence reports on healthcare providers. Users enter a provider's name and receive a detailed report within ~10 minutes, synthesizing data from 6+ source categories (federal registries, state licensing boards, court records, commercial directories, review platforms, insurance networks) with full provenance and confidence scoring.

---

## Where the Code Lives

| Resource | Location |
|----------|----------|
| Build repo | https://github.com/Alijrob/medpro-review |
| Blueprint repo (planning docs, adversarial reviews) | https://github.com/Alijrob/blueprint-medical-professionals-review-1779589432732 |
| Phase tracker | `/root/pagios-ops/trackers/medpro-review-phase-tracker.md` |
| Architecture lock | `docs/reference/architecture-lock.md` |
| Component roster | `docs/reference/component-roster.md` |
| Tool recommendations | `docs/reference/tool-recommendations.md` |

---

## Current Phase

**Phase 1-I COMPLETE** — Audit Ledger Service (`src/backend/audit_service/`, component C5-audit): the append-only, hash-chained ledger that replaces QLDB (Entry 005). `ledger.py` assigns `prev_event_hash`/`event_hash` per `(target_type, target_id)` chain, appends immutably, and verifies by recomputation (detects altered contents and removed/reordered events); FastAPI surface for append/chain/verify/checkpoint; 15 behavior tests; runs via `make run-audit`. Deploys to the `workers` namespace (internal-only ClusterIP, NetworkPolicy baseline); Aurora-only (S3 WORM = Phase 4-F). DECISIONS.md Entry 013. Phase 1 foundations complete; Phase 2-A (Source Connector Framework) is next.
**Phase 1-H COMPLETE** — OPA Baseline (component C2): policy bundle in `src/policy/` (`medpro.authz` + `medpro.redaction`, 16 `opa test` units), delivered as the `opa-policy` ConfigMap by a sync-wave -1 ArgoCD app; OPA sidecar added to the gateway pod (localhost:8181) with `OPA_ENABLED=true` flipped on in-cluster (local dev stays off); NetworkPolicy baseline for the `api-gateway` namespace (default-deny + Entry 011 cross-namespace allows). DECISIONS.md Entry 012.
**Phase 1-G COMPLETE** — API Gateway shell (`src/backend/api_gateway/`, component C8): FastAPI gateway that mounts the 1-F auth overlay and adds rate limiting, idempotency, request-id, security headers, and an OPA authz hook (C2 baseline). Deployable via a `workloads` ArgoCD app-of-apps into the `api-gateway` namespace (DECISIONS.md Entry 011). 15 behavior tests; runs via `make run-gateway`.
**Phase 1-F COMPLETE** — Auth & Identity Service shell (`src/backend/auth_service/`, C7): Auth0 JWT validation (RS256/JWKS), RBAC gates, Path B permissible-use gate. `make run-backend`.
**Phase 1-E COMPLETE** — GitOps + CI/CD skeleton: ArgoCD app-of-apps (`src/gitops/`), pinned Helm charts, sync waves, PrometheusRule parity guard, kustomize ConfigMap overlays, deploy-time PLACEHOLDER guard. Non-deployed.
**Path B (non-CRA) locked** — See DECISIONS.md entries 004-007.
**Legal gate still active** — FCRA determination pending. IaC skeletons, schema, data layer, observability, and GitOps config are safe to build; no running services until gate closes.
**IaC + observability + GitOps are non-deployed** — DECISIONS.md Entry 003 (AWS account/region) must be resolved before `terragrunt apply` or any ArgoCD sync.
**Domain locked** — researchyourdoctor.com (DECISIONS.md Entry 008).
**Auth provider locked** — Auth0 (DECISIONS.md Entry 002, resolved 2026-05-25).
**Sentry hosting locked** — SaaS, PII scrubbed before egress (DECISIONS.md Entry 009, resolved 2026-05-25).
**Open before deploy** — OTel gateway config-mount wiring (Entry 010); AWS account/region (Entry 003).

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0-A | Repo + docs bootstrap | ✅ Complete |
| 0-B | FCRA architectural blueprints | ✅ Complete |
| 0-C | ToS analysis matrix (80 sources) | ✅ Complete |
| 0-D | Source priority matrix (P1/P2/P3 tiers, Phase 2 build sequence) | ✅ Complete |
| 0-E | Data licensing cost model (unit economics, CRA delta, break-even) | ✅ Complete |
| **Path B lock** | DECISIONS.md entries 004-007 (non-CRA, QLDB removed, C23 removed, C20/C22/OPA/retention rescoped) | ✅ Complete |
| 1-A | Canonical Schema v1 — Pydantic models + schema registry | ✅ Complete |
| 1-B | Infrastructure Terraform Skeleton (non-deployed) | ✅ Complete |
| 1-C | Data Store Baseline (migrations, OpenSearch, Redis, docker-compose) | ✅ Complete |
| 1-D | Observability Stack Config (OTel, Prometheus, Loki, Tempo, Grafana, Sentry) | ✅ Complete |
| 1-E | GitOps + CI/CD Skeleton (ArgoCD app-of-apps, sync waves, pinned charts) | ✅ Complete |
| 1-F | Auth Service Shell (C7 — Auth0 JWT validation, RBAC, Path B gate) | ✅ Complete |
| 1-G | API Gateway Shell (C8 — auth overlay, rate limit, idempotency, OPA hook) | ✅ Complete |
| 1-H | OPA Baseline (C2 — policy bundle, sidecar, NetworkPolicies) | ✅ Complete |
| 1-I | Audit Ledger Service (C5-audit — append-only, hash-chained) | ✅ Complete |
| 2-A | Source Connector Framework | 🔄 Up next |

---

## How to Install (Local Dev)

> Prerequisites: macOS or Linux, Git, Docker Desktop running.

```bash
git clone https://github.com/Alijrob/medpro-review.git
cd medpro-review
make dev-setup
```

The `make dev-setup` script (`scripts/dev-setup.sh`) is idempotent and installs:
- Python 3.11+ (via pyenv if needed)
- Poetry (dependency manager)
- Node.js LTS (via nvm if needed)
- AWS CLI
- kubectl + helm + terragrunt + ArgoCD CLI
- direnv

---

## How to Run

```bash
make run-backend     # auth service (FastAPI)   on :8000 — OpenAPI at /docs
make run-gateway     # API gateway (FastAPI)     on :8080 — OPA off locally (no sidecar)
make run-audit       # audit ledger (FastAPI)    on :8001 — in-memory chain
make run-frontend    # Next.js dev server (src/frontend/)
```

> `make run-backend` launches the Phase 1-F auth service shell (`backend.auth_service.app:app`). The frontend target is still a stub until Phase 2-K. Auth0 env vars are optional locally — with them blank the service boots, but token validation fails closed (401) and `/readyz` returns 503. The gateway and audit ledger run without Auth0/OPA/DB locally (shells).

---

## How to Deploy

- **Dev:** Automatic on every merge to `main` via ArgoCD
- **Staging:** Manual gate — trigger `staging-deploy` workflow in GitHub Actions
- **Production:** Manual gate — requires Product + Engineering + Legal sign-off

> Note: No deployment environments exist yet. EKS provisioning is Phase 1-B.

---

## Required Environment Variables

> Auth service vars are active as of Phase 1-F (blank-safe locally). The rest populate as services are built.

| Variable | Purpose | Phase Set |
|----------|---------|-----------|
| `AUTH0_DOMAIN` | Auth0 tenant domain (e.g. `medpro.us.auth0.com`) — JWKS + issuer | Phase 1-F (active) |
| `AUTH0_AUDIENCE` | Auth0 API identifier (the `aud` claim validated) | Phase 1-F (active) |
| `AUTH0_ISSUER` | Optional issuer override (defaults to `https://{AUTH0_DOMAIN}/`) | Phase 1-F (active) |
| `AUTH0_CLIENT_ID` | Frontend auth | Phase 2-K |
| `AUTH0_CLIENT_SECRET` | Server-side OAuth flows (if needed) | Phase 2-K |
| `STRIPE_SECRET_KEY` | Payment processing | Phase 2-J |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook validation | Phase 2-J |
| `DATABASE_URL` | Aurora PostgreSQL | Phase 1-B (dev: local Postgres) |
| `REDIS_URL` | Cache / rate limiting | Phase 1-B (dev: local Redis) |
| `OPENSEARCH_URL` | Provider search | Phase 1-B |
| `AUDIT_DATABASE_URL` | Aurora `medpro_audit` DB (connect as `medpro_audit_writer`, INSERT-only) — replaces QLDB (Entry 005) | Phase 1-I (active in deploy) |
| `TEMPORAL_ADDRESS` | Workflow orchestration | Phase 2-H |
| `AWS_REGION` | AWS services | Phase 1-B |
| `OPA_ENABLED` | Switches on the gateway's fail-closed authz hook (set `true` in-cluster; code default `false`) | Phase 1-H (active in deploy) |
| `OPA_URL` | OPA sidecar decision API (in-cluster: `http://127.0.0.1:8181`) | Phase 1-H (active in deploy) |

All secrets managed via AWS Secrets Manager + Kubernetes External Secrets Operator in deployed environments.

---

## Important Files

| File | Purpose |
|------|---------|
| `docs/reference/architecture-lock.md` | **Read before writing any code** — locked architecture |
| `docs/reference/component-roster.md` | C1-C26 component reference and phase mapping |
| `docs/reference/tool-recommendations.md` | Locked stack, libraries, and what to avoid |
| `docs/reference/fcra-blueprints.md` | CRA vs. non-CRA architectural blueprints for legal counsel |
| `docs/reference/tos-matrix.md` | ToS analysis matrix — 80 sources, risk tiers, legal sign-off status |
| `docs/reference/source-priority.md` | Source Priority Matrix — P1/P2/P3 ranking, Phase 2 adapter build sequence |
| `docs/reference/cost-model.md` | Data Licensing Cost Model — unit economics, CRA delta, break-even analysis |
| `DECISIONS.md` | Log of all deviations from the locked plan (entries 001-009 current) |
| `src/schema/v1/` | Canonical Pydantic v2 schema — read before writing any data layer code |
| `src/schema/registry.py` | Schema registry for drift detection and JSON Schema export |
| `tests/schema/test_v1_models.py` | 44-test suite for schema models — run with `PYTHONPATH=src pytest tests/` |
| `src/infrastructure/terragrunt.hcl` | Terragrunt root — S3 remote state, AWS provider generation |
| `src/infrastructure/environments/{env}/env.hcl` | Per-environment config (account, region, domain — all PLACEHOLDER until Entry 003 resolved) |
| `src/infrastructure/modules/` | 9 Terraform modules: vpc, kms, s3, iam, ecr, aurora, elasticache, opensearch, eks |
| `src/infrastructure/README.md` | IaC deploy instructions, env differences, deploy order |
| `src/data/migrations/versions/` | Alembic migrations 0001-0003 (baseline schema, audit schema, roles/RLS/seeds) |
| `src/data/opensearch/providers_index_template.json` | OpenSearch index template for `providers-*` pattern |
| `src/data/redis/keyspace-strategy.md` | Redis key patterns, TTLs, eviction policy — read before adding cache keys |
| `docker-compose.dev.yml` | Local dev stack: Postgres 15, Redis 7, OpenSearch 2.11 |
| `scripts/dev-init-postgres.sql` | Creates medpro_audit DB and installs extensions (run once after docker-compose up) |
| `src/data/README.md` | Data layer quick-reference: how to run migrations, apply OS template, run tests |
| `src/observability/README.md` | Observability quick-reference: signal flow, layout, PII handling, deploy order |
| `src/observability/otel-collector/collector-config.yaml` | OTel gateway pipeline (OTLP in → Tempo/Prometheus/Loki out, PII scrub) |
| `src/observability/prometheus/rules/` | Recording + alerting rules (service SLO, source health, audit ledger, pipeline) |
| `src/observability/grafana/dashboards/` | Pipeline SLO, Source Health, Audit Ledger dashboards (JSON) |
| `src/observability/sentry/sentry_config.py` | Shared Sentry init — mandatory PII scrubbing, DSN from env |
| `tests/observability/test_observability_config.py` | 39-test suite — run with `make obs-validate` |
| `src/gitops/README.md` | **GitOps quick-reference** — app-of-apps, sync waves, pinned charts, deploy steps |
| `src/gitops/charts-lock.yaml` | Pinned Helm chart versions — single source of truth for every ArgoCD app |
| `src/gitops/argocd/bootstrap/root-app.yaml` | The app-of-apps root Application (apply after ArgoCD install) |
| `src/gitops/argocd/apps/` | One child Application per platform component, sync-waved |
| `src/gitops/argocd/monitoring/` | PrometheusRule CRD wrappers (parity-tested against 1-D rules) |
| `scripts/gitops-guard.sh` | Deploy-time PLACEHOLDER guard — blocks ArgoCD sync until Entry 003 |
| `tests/gitops/test_gitops_config.py` | 138-test suite — run with `make gitops-validate` |
| `src/backend/auth_service/README.md` | **Auth service quick-reference** — endpoints, token model, Path B gate, run/test |
| `src/backend/auth_service/dependencies.py` | The reusable auth overlay — `get_current_user`, `require_roles/permissions`, Path B gate |
| `src/backend/auth_service/security.py` | Auth0 JWT verification (JWKS cache, RS256, iss/aud/exp) |
| `src/backend/api_gateway/README.md` | **API gateway quick-reference** — concerns, endpoints, topology, run/test |
| `src/backend/api_gateway/middleware.py` | Rate limit, idempotency, request-id, security headers |
| `src/backend/api_gateway/opa.py` | OPA authz hook (C2 baseline) — `require_authz(action, resource)` |
| `src/backend/api_gateway/deploy/` | kustomize Deployment (+ OPA sidecar) + Service + NetworkPolicies (api-gateway namespace, IRSA SA) |
| `src/gitops/argocd/workloads/` | Workload ArgoCD child apps (api-gateway, opa-policy); `workloads` AppProject |
| `tests/backend/test_api_gateway.py` | 15 behavior tests (auth chain, rate limit, idempotency, OPA) |
| `src/policy/` | **OPA policy bundle (C2)** — `authz.rego` + `redaction.rego`, `opa test` units, `opa-policy` ConfigMap kustomization |
| `src/policy/README.md` | OPA quick-reference — packages, sidecar model, authz/redaction contracts, validate |
| `src/gitops/argocd/workloads/opa-policy.yaml` | Delivers the policy bundle to the api-gateway namespace (sync-wave -1) |
| `src/backend/audit_service/ledger.py` | **Audit ledger core (C5-audit)** — per-target hash chaining, append, verify, checkpoints |
| `src/backend/audit_service/README.md` | Audit service quick-reference — endpoints, chain model, topology, run/test |
| `src/backend/audit_service/deploy/` | kustomize Deployment + Service + NetworkPolicies (workers namespace, workers-sa) |
| `src/gitops/argocd/workloads/audit-service.yaml` | Audit service ArgoCD child app (workers namespace) |
| `tests/backend/test_audit_service.py` | 15 behavior tests (append/hash, chain linkage, tamper detection, checkpoints) |
| `docs/session-logs/` | Per-session build logs |

---

## Known Blockers

1. **Phase 0 Legal Gate** — FCRA determination is blocking all engineering code. ETA: 16 weeks from legal engagement start.
2. ~~Auth0 vs. Okta selection~~ — RESOLVED: **Auth0** (DECISIONS.md Entry 002, 2026-05-25).
3. **AWS account / region** — Not yet assigned. Blocks Phase 1-B (IaC) and Phase 1-D (observability) from being deployable. Domain is locked (researchyourdoctor.com, Entry 008). (See DECISIONS.md Entry 003.)
4. **Ground truth dataset** — Required for C12 identity resolution >98% precision target. Must be assigned an owner before Phase 2-E.
5. ~~Sentry hosting mode~~ — RESOLVED: **SaaS** (DECISIONS.md Entry 009, 2026-05-25). Region pinned at wiring time; revisit if actual PHI is ever ingested.

---

## Next Likely Step

**Phase 2-A:** Source Connector Framework (C9) — the base classes, error handling, throttling, retry/backoff, and contract-testing harness that every source adapter (C10, Phase 2-B onward) builds on. This opens **Phase 2 (Core Identity & MVP)**; all Phase 1 foundations (schema, IaC, data, observability, GitOps, auth, gateway, OPA, audit ledger) are complete. The Phase 0 legal gate still governs anything that ingests real source data.

**Phase 1-I audit service validates locally (no DB/cluster needed):**
```bash
PYTHONPATH=src pytest tests/backend/test_audit_service.py -v   # 15 behavior tests
make run-audit                                    # uvicorn on :8001, /docs
kustomize build src/backend/audit_service/deploy  # Deployment + Service + NetworkPolicies
```

**Phase 1-H OPA bundle validates locally (requires the `opa` CLI; no cluster needed):**
```bash
make opa-test                          # opa check + 16 unit tests
kustomize build src/policy             # opa-policy ConfigMap renders
kustomize build src/backend/api_gateway/deploy   # Deployment (+ opa sidecar) + Service + NetworkPolicies
```

**Phase 1-F/1-G backend validates locally (no Auth0/network/cluster needed):**
```bash
PYTHONPATH=src pytest tests/backend/ -v
# Expected: 32 passed (17 auth + 15 gateway)

make run-backend   # auth service  — uvicorn on :8000
make run-gateway   # API gateway   — uvicorn on :8080 (OPA off locally — no sidecar)
```

**Phase 1-E GitOps config validates locally (no cluster needed):**
```bash
make gitops-validate
# Expected: 138 passed
kustomize build src/observability/grafana          # ConfigMaps render
kustomize build src/observability/otel-collector
```

**Phase 1-D observability config validates locally (no cluster needed):**
```bash
make obs-validate
# Expected: 39 passed
```

**Phase 1-C data store is operational locally:**
```bash
# Start all data stores
docker compose -f docker-compose.dev.yml up -d

# Run dev-init-postgres.sql once (creates medpro_audit DB + extensions)
docker exec -i medpro-postgres psql -U medpro_admin -f /scripts/dev-init-postgres.sql

# Apply Alembic migrations
DATABASE_URL=postgresql+psycopg2://medpro_admin:devpass@localhost:5432/medpro \
  alembic -c src/data/migrations/alembic.ini upgrade head

# Run data layer unit tests (no DB required)
PYTHONPATH=src pytest tests/data/ -v -m "not integration"
# Expected: 20 passed
```

**Phase 1-B IaC is ready to apply once Entry 003 is resolved:**
```bash
# Fill in environments/dev/env.hcl (aws_account, aws_region, domain)
make infra-init ENV=dev
make infra-plan ENV=dev
make infra-apply ENV=dev
```

**Parallel actions still open:**
1. Engage FSMB DocInfo for enterprise API pricing
2. Engage ABMS for enterprise subscription pricing
3. Engage Ribbon Health for pricing tiers
4. Engage general counsel for Path B ToS review (not FCRA-specialized — Path B locked)
5. Resolve T4 architectural decisions (Healthgrades, Vitals, Doximity) — DECISIONS.md Entry 006 context
6. Lock Auth0 vs. Okta (DECISIONS.md Entry 002)
7. Lock AWS account, region, and domain (DECISIONS.md Entry 003)

**To run schema tests:**
```bash
cd medpro-review
PYTHONPATH=src pytest tests/schema/ -v
# Expected: 44 passed
```

**To validate IaC (requires terraform CLI):**
```bash
make infra-validate
```
