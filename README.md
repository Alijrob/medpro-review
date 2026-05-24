# Medical Professionals Review

**Healthcare Provider Intelligence & Vetting Platform**

A consumer-facing service that generates comprehensive, transparent intelligence reports on healthcare providers — synthesizing data from 6+ source categories (federal registries, state licensing boards, court records, commercial directories, review platforms, insurance networks) with full provenance tracking.

## Status

**Phase 0-A complete** — Repo bootstrapped, architecture reference docs loaded, phase tracker created.
**Phase 0 (Legal Gate) is BLOCKING all engineering.** No backend/frontend/infra code may be written until the FCRA determination is in hand.

## Architecture

This project is built to a locked architecture. Read before writing any code:

- [`docs/reference/architecture-lock.md`](docs/reference/architecture-lock.md) — Full locked architecture + adversarial review resolution
- [`docs/reference/tool-recommendations.md`](docs/reference/tool-recommendations.md) — Locked stack and library choices
- [`docs/reference/component-roster.md`](docs/reference/component-roster.md) — C1-C26 component reference

## Blueprint Repo

Planning artifacts, adversarial reviews, and final plan live in the companion blueprint repo:
**[Alijrob/blueprint-medical-professionals-review-1779589432732](https://github.com/Alijrob/blueprint-medical-professionals-review-1779589432732)**

## Phase Tracker

Master tracker: `pagios-ops/trackers/medpro-review-phase-tracker.md`

## Stack (Locked)

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js + TypeScript |
| Orchestration | Temporal |
| Policy | Open Policy Agent (OPA) |
| Audit Ledger | AWS QLDB + S3 streams |
| Primary DB | AWS Aurora PostgreSQL |
| Cache | AWS ElastiCache (Redis) |
| Search | OpenSearch |
| Storage | AWS S3 |
| Cloud | AWS (EKS) |
| IaC | Terraform / Terragrunt |
| GitOps | ArgoCD |
| CI/CD | GitHub Actions |
| Auth | Auth0/Okta + custom overlay |
| Observability | OpenTelemetry -> Prometheus, Loki, Tempo, Grafana, Sentry |
| Payments | Stripe |

## Developer Setup

```bash
make dev-setup
make run-backend
make run-frontend
```

See [`docs/setup/onboarding.md`](docs/setup/onboarding.md) for full instructions.

## Folder Structure

```
src/
  backend/         FastAPI services
  frontend/        Next.js app
  workers/         Temporal workflow workers
  infrastructure/  Terraform / Terragrunt / Helm
  shared/          Pydantic schemas, types (shared across services)
docs/
  setup/           Onboarding + install
  reference/       Architecture docs
  session-logs/    Per-session build logs
scripts/
  dev-setup.sh     Idempotent local dev environment setup
.github/workflows/ CI/CD pipelines
DECISIONS.md       Deviations from the locked architecture plan
```
