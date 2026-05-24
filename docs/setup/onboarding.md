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

**Phase 0-A COMPLETE** — Repo bootstrapped, all reference docs loaded, tracker created.
**Phase 0 (Legal Gate) is BLOCKING all engineering code.**

No backend, frontend, or infrastructure code may be written until the FCRA determination is in hand from legal counsel. Only documentation, IaC skeletons (non-deployed), and schema design files are safe to produce during Phase 0.

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
| `QLDB_LEDGER_NAME` | Audit ledger | Phase 1-I |
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
| `DECISIONS.md` | Log of all deviations from the locked plan |
| `docs/session-logs/` | Per-session build logs |

---

## Known Blockers

1. **Phase 0 Legal Gate** — FCRA determination is blocking all engineering code. ETA: 16 weeks from legal engagement start.
2. **Auth0 vs. Okta selection** — Must be locked before Phase 1-F starts. (See DECISIONS.md Entry 002.)
3. **AWS account / region / domain** — Not yet assigned. Blocks Phase 1-B from being deployable. (See DECISIONS.md Entry 003.)
4. **Ground truth dataset** — Required for C12 identity resolution >98% precision target. Must be assigned an owner before Phase 2-E.

---

## Next Likely Step

**Phase 0-B:** Write the two parallel FCRA architectural blueprint summaries (CRA path vs. non-CRA path) for legal counsel review. Output: `docs/reference/fcra-blueprints.md`.
