# Onboarding — Medical Professionals Review

**Project:** Healthcare Provider Intelligence & Vetting Platform
**Product:** Medical Professionals Review
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

**Phase 1-B COMPLETE** — Terraform/Terragrunt IaC skeleton shipped. Phase 1-C (Data Store Terraform Modules) is next.
**Path B (non-CRA) locked** — See DECISIONS.md entries 004-007.
**Legal gate still active** — FCRA determination pending. IaC skeletons and schema are safe to build; no running services until gate closes.
**IaC is non-deployed** — DECISIONS.md Entry 003 (AWS account/region/domain) must be resolved before `terragrunt apply`.

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
| 1-C | Data Store Terraform Modules | 🔄 Up next |

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
make run-backend     # FastAPI dev server (src/backend/)
make run-frontend    # Next.js dev server (src/frontend/)
```

> Note: Neither service exists yet. These targets will be populated starting Phase 1-F (Auth Service) and Phase 2-K (Frontend Phase 1).

---

## How to Deploy

- **Dev:** Automatic on every merge to `main` via ArgoCD
- **Staging:** Manual gate — trigger `staging-deploy` workflow in GitHub Actions
- **Production:** Manual gate — requires Product + Engineering + Legal sign-off

> Note: No deployment environments exist yet. EKS provisioning is Phase 1-B.

---

## Required Environment Variables

> None active yet. Variables will be populated as services are built.

| Variable | Purpose | Phase Set |
|----------|---------|-----------|
| `AUTH0_DOMAIN` or `OKTA_DOMAIN` | IDaaS auth | Phase 1-F |
| `AUTH0_CLIENT_ID` | Frontend auth | Phase 1-F |
| `AUTH0_CLIENT_SECRET` | Backend JWT validation | Phase 1-F |
| `STRIPE_SECRET_KEY` | Payment processing | Phase 2-J |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook validation | Phase 2-J |
| `DATABASE_URL` | Aurora PostgreSQL | Phase 1-B (dev: local Postgres) |
| `REDIS_URL` | Cache / rate limiting | Phase 1-B (dev: local Redis) |
| `OPENSEARCH_URL` | Provider search | Phase 1-B |
| `AUDIT_LOG_TABLE` | Aurora append-only audit table name (replaces QLDB — see DECISIONS.md Entry 005) | Phase 1-I |
| `TEMPORAL_ADDRESS` | Workflow orchestration | Phase 2-H |
| `AWS_REGION` | AWS services | Phase 1-B |
| `OPA_URL` | Policy engine sidecar | Phase 1-H |

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
| `DECISIONS.md` | Log of all deviations from the locked plan (entries 001-007 current) |
| `src/schema/v1/` | Canonical Pydantic v2 schema — read before writing any data layer code |
| `src/schema/registry.py` | Schema registry for drift detection and JSON Schema export |
| `tests/schema/test_v1_models.py` | 44-test suite for schema models — run with `PYTHONPATH=src pytest tests/` |
| `src/infrastructure/terragrunt.hcl` | Terragrunt root — S3 remote state, AWS provider generation |
| `src/infrastructure/environments/{env}/env.hcl` | Per-environment config (account, region, domain — all PLACEHOLDER until Entry 003 resolved) |
| `src/infrastructure/modules/` | 9 Terraform modules: vpc, kms, s3, iam, ecr, aurora, elasticache, opensearch, eks |
| `src/infrastructure/README.md` | IaC deploy instructions, env differences, deploy order |
| `docs/session-logs/` | Per-session build logs |

---

## Known Blockers

1. **Phase 0 Legal Gate** — FCRA determination is blocking all engineering code. ETA: 16 weeks from legal engagement start.
2. **Auth0 vs. Okta selection** — Must be locked before Phase 1-F starts. (See DECISIONS.md Entry 002.)
3. **AWS account / region / domain** — Not yet assigned. Blocks Phase 1-B from being deployable. (See DECISIONS.md Entry 003.)
4. **Ground truth dataset** — Required for C12 identity resolution >98% precision target. Must be assigned an owner before Phase 2-E.

---

## Next Likely Step

**Phase 1-C:** Data Store Terraform Modules — Flyway/Alembic migration baseline for Aurora, index definitions for OpenSearch, Redis keyspace strategy document.

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
