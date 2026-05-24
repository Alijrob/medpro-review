# Tool Recommendations — Medical Professionals Review

**Locked as of:** 2026-05-24
**Source:** Architecture Lock Report (Senior Engineering Lead)

---

## Locked Stack

| Layer | Tool | Version | Justification |
|-------|------|---------|--------------|
| Backend | FastAPI | Python 3.11+ | Async, Pydantic-native, high performance |
| Frontend | Next.js + React + TypeScript | Latest stable | SSR, SEO, performance |
| Orchestration | Temporal | Latest stable | Durable, fault-tolerant, auditable workflows |
| Policy | Open Policy Agent (OPA) + Rego | Latest stable | Declarative, decoupled from code, auditable |
| Audit Ledger | AWS QLDB | Managed | Cryptographic verifiability, FCRA-grade |
| Primary DB | AWS Aurora PostgreSQL | PostgreSQL 14/15 compatible | ACID, managed HA, open-source compatible |
| Cache/Rate Limit | AWS ElastiCache (Redis) | 7.0+ | High-speed in-memory, session, rate limiting |
| Search | OpenSearch | Latest stable | Open-source, scalable, faceted search |
| Object Store | AWS S3 | - | Durable, cost-effective |
| Cloud | AWS | - | Single-cloud MVP |
| Containers | AWS EKS (Kubernetes) | 1.27+ | Portable compute layer |
| IaC | Terraform / Terragrunt | 1.5+ / 0.47+ | Declarative, auditable |
| GitOps | ArgoCD | Latest stable | Automated K8s deployment |
| CI/CD | GitHub Actions | - | Integrated with repo |
| Auth | Auth0 or Okta | Latest SDKs | IDaaS, minimize internal security burden |
| Observability | OpenTelemetry -> Prometheus, Loki, Tempo, Grafana, Sentry | Latest | Open standard, vendor-neutral |
| Secrets | AWS Secrets Manager + External Secrets Operator | - | Least-privilege secret injection |
| Payments | Stripe | Latest SDKs | Subscriptions, webhooks, customer portal |
| Schema (Python) | Pydantic V2+ | V2+ | Strong types, FastAPI native |
| Schema (TS) | Zod / Yup | Latest | Runtime validation, type-safe |

---

## Development Tooling

### Python
- `Poetry` — dependency management and virtual environments
- `Black` — code formatter
- `isort` — import sorter
- `Flake8` — linter
- `MyPy` — static type checker
- `pytest` + `pytest-asyncio` — testing framework

### TypeScript / JavaScript
- `ESLint` — linter
- `Prettier` — code formatter
- `Jest` + `React Testing Library` — component testing

### Infrastructure
- `Docker Desktop` — local containers
- `AWS CLI` — cloud management
- `kubectl` — Kubernetes CLI
- `helm` — Kubernetes package manager
- `terragrunt` — Terraform wrapper (DRY, remote state)
- `ArgoCD CLI` — deployment management

### Local Dev
- `make` or `just` — task runner (`make dev-setup`, `make test`, `make lint`, `make infra-plan`)
- `direnv` — automatic env var loading per directory

---

## Key Libraries

### Data Validation & Serialization
- Python: `Pydantic V2+`
- TypeScript: `Zod` or `Yup`

### Database ORM
- Python: `SQLAlchemy 2.0+` with `asyncpg` driver

### HTTP Client
- Python: `httpx` (async-first)
- TypeScript: `TanStack Query (React Query)` + `axios` or `fetch`

### Identity Resolution / ML
- `Splink` or `dedupe.io` — probabilistic record linkage
- `scikit-learn`, `pandas`, `numpy` — data manipulation and ML

### Temporal SDK
- Python: `temporalio`

### OPA Integration
- Python: `python-opa` or direct HTTP client to OPA sidecar

### AWS SDKs
- Python: `boto3`
- TypeScript: `@aws-sdk/client-s3`, `@aws-sdk/client-secrets-manager`, etc.

### Observability
- Python: `opentelemetry-instrumentation-fastapi`, `opentelemetry-sdk`
- TypeScript: `@opentelemetry/sdk-node`

### PDF Generation
- Python: `WeasyPrint` — HTML/CSS -> PDF

### Authentication
- Python: `python-jose` + `auth0-python` (or Okta equivalent)
- TypeScript: `nextjs-auth0` (or `@okta/okta-react`)

### Logging
- Python: `structlog` — structured logging
- TypeScript: `pino` or `winston`

### Academic / Data Sources
- Python: `BioPython` (PubMed); `stripe-python`, `yelpapi`, `google-api-python-client`
- TypeScript: `stripe-js`, `@stripe/react-stripe-js`

---

## What to Avoid

- Ad-hoc data scraping without legal review and C9 framework
- Homegrown authentication or authorization
- Direct database access from frontend
- Manual infrastructure management (ClickOps)
- Proprietary AWS-specific observability lock-in (use OpenTelemetry)
- Monolithic architecture
- Blindly trusting external data sources
- Ignoring compliance-first principles (OPA, QLDB are non-negotiable)
- Premature custom ML — start with Splink/dedupe.io

---

## Workflow Pattern

### Branching
- GitHub Flow: `main` always deployable; feature branches for all work; PRs to merge

### PR Process
- Automated checks: Black, isort, Flake8, ESLint, Prettier, pytest, Jest, SAST
- Mandatory peer review; branch protection on `main`
- Conventional Commits format

### Environments
- `dev` — auto-deploys every merge to `main`
- `staging` — manual gate; realistic data subsets; full integration tests
- `production` — manual gate; requires Product + Engineering + Legal sign-off; weekly release train; on-demand for hotfixes

### Rollback
- All ArgoCD deployments support rapid automated rollback
- DB migrations must be backward-compatible or include rollback scripts

---

## Onboarding Checklist (New Developer — Target: 2 hours)

1. Account Access (30 min): GitHub, AWS SSO, Auth0/Okta dev credentials, VPN
2. Core Tools (45 min): VS Code + extensions, Docker Desktop, AWS CLI, kubectl, helm, terragrunt, ArgoCD CLI, Poetry, Node.js LTS
3. Project Setup (30 min): `git clone`, `make dev-setup` (installs deps, hooks, direnv, local DB)
4. Verify (15 min): `make run-backend-dev`, `make run-frontend-dev`, open `localhost:3000`, `make test`
