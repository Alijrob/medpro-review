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

**Phase 3-C COMPLETE** -- PACER + State Court Adapters. 5 new `SourceConnector` subclasses in `src/connectors/sources/court_records/`: `CourtListenerConnector` (REST_API, page-number/next-null termination), `PacerConnector` (REST_API, 0-indexed page-number with totalPages termination), `TxCourtsConnector` (REST_API offset/limit), `FlCourtsConnector` (REST_API offset/limit), `NyCourtsConnector` (REST_API page-number/next-null + bare list). All use `SourceCategory.COURT`, carry `_FIELD_MAP` normalizing camelCase/alias variants, normalize `None` to `""`, and accept auth tokens as constructor args (not config). CourtListener: `docket_id` coerced from int to str. PACER: `X-NEXT-GEN-CSO` header; 0-indexed pages. NY eCourts: bare list response accepted; `caseCaption`/`captionOnFiling` -> `caption`; `rjiStatus` -> `status`. Migration 0009 seeds 5 court_* source_health_records rows (category='court'); chains from 0008; ON CONFLICT DO NOTHING. `court_records/__init__.py` + `sources/__init__.py` updated. 82 new tests (1595 total, 18 skipped). DECISIONS.md Entry 038. **Phase 3-D (Commercial Data Adapters) is next.**
**Phase 3-B COMPLETE** -- State Board Adapters, Next 5 States (GA/PA/OH/MI/NC). 5 new `SourceConnector` subclasses in `src/connectors/sources/state_boards/`: `GaCompositeMedicalBoardConnector` (SODA, data.georgia.gov), `PaMedicalBoardConnector` (SODA, data.pa.gov), `OhStateMedicalBoardConnector` (REST_API offset, elicense.ohio.gov), `MiLaraConnector` (SODA, data.michigan.gov), `NcMedicalBoardConnector` (REST_API page-number, ncmedboard.org). All carry `_FIELD_MAP` normalizing camelCase/SODA column variants to contract snake_case. All 5 use 6-field contracts; NC uses `specialty` instead of `license_type` (matching TX pattern). Migration 0008 seeds 5 new `source_health_records` rows (state_board_ga/pa/oh/mi/nc, status=unknown, category=state_board); chains from 0007; ON CONFLICT DO NOTHING. `state_boards/__init__.py` updated with Phase 3-B exports. 83 new tests (1513 total, 18 skipped). DECISIONS.md Entry 037. **Phase 3-C (PACER + State Court Adapters) is next.**
**Phase 2-N COMPLETE** -- PDF Report Generation (WeasyPrint). `src/report/pdf.py` -- `render_pdf(html: str) -> bytes`; soft import (`WEASYPRINT_AVAILABLE` flag; no system deps required in dev/CI); `render_pdf` exported from `src/report/__init__.py`. `GET /v1/reports/{report_id}/pdf` in report service: UUID first, then DB check, then payment gate (402 if not paid), then report-complete gate (409 if queued/failed), then HTML presence check (422 if null), then WeasyPrint availability check (501 if missing), then render; returns `application/pdf` with `Content-Disposition: attachment; filename="medpro-report-{npi}-{id[:8]}.pdf"`. `ReportRepository.get_row()` now returns `payment_status` + raw `report_html` string. `ReportStatusResponse` now includes `payment_status: str = "unpaid"`. Next.js proxy: `GET /api/reports/[id]/pdf` (30s timeout, streams arrayBuffer). "Download PDF" anchor in `ReportViewer.tsx` -- visible only when `isComplete(status) && payment_status === 'paid'`. 12 new pytest tests (all 200-path tests monkeypatch `render_pdf` -- no WeasyPrint system deps needed). 1430 total. DECISIONS.md Entry 036. **Phase 3-B (State Board Adapters, Next 5 States) is next.**
**Phase 2-M COMPLETE** -- E2E Playwright Test Harness. Playwright config in `src/frontend/playwright.config.ts`. All backend services + Auth0 mocked via `page.route()` -- no live services needed. 5 spec files (21 tests): landing (4), certify (4), search (5), payment (4), report-poll (4). Mock strategy: `page.route()` intercepts at browser level (preferred over MSW for Next.js App Router). `storageState` for auth session. Fixture JSON in `tests/e2e/fixtures/`. `MockState.reportCallCount` simulates polling transitions. CI: `.github/workflows/e2e-validate.yml` (build + start + playwright test + artifact). `make e2e-test`. DECISIONS.md Entry 034. Python test count unchanged (1333). **Phase 3-A (State Board Adapters) is next.**
**Phase 2-L COMPLETE** -- Auth0 + Stripe Integration Wiring. Fixed live 422 bug: `success_url` and `cancel_url` are now injected server-side at the payments proxy (`/api/payments/checkout/route.ts`) -- client never constructs Stripe URLs. Added `POST /v1/users/sync` to the payment service (`src/backend/payment_service/routes.py`): links Auth0 `sub` to the `users` row after login (server-to-server, no JWT, best-effort). Added `PaymentRepository.link_auth_sub()`. Added `/api/auth/sync/route.ts` Next.js proxy route. Customized `handleAuth` `afterCallback` to call sync endpoint after login. Added `/terms` placeholder page. Updated `.env.local.example` with `NEXT_PUBLIC_APP_URL`. 15 new Python tests. 1333 total. DECISIONS.md Entry 033. **Phase 2-M (E2E Playwright) is next.**
**Phase 2-K COMPLETE** -- Frontend Phase 1 (Auth + Search + Report Viewer). Next.js 14 App Router frontend shell in `src/frontend/`. Non-deployed (Entry 003 + legal gate). `@auth0/nextjs-auth0` v3 for Auth0 Universal Login (`/api/auth/[...auth0]/route.ts`). `withMiddlewareAuthRequired()` protects `/search`, `/reports`, `/certify`. API Route proxy layer: browser never calls backend services directly (GET /api/search -> :8003, POST /api/reports -> :8004, GET /api/reports/[id] -> :8004, POST /api/payments/checkout -> :8005). Pages: `/` landing, `/certify` Path B cookie gate (legal use_agreements at payment time), `/search` TanStack Query provider search, `/reports/[id]` ReportStatusPoller (3s polling). Components: SearchBar, ProviderCard, SearchResults, ReportStatusPoller, PaymentGate (Stripe redirect), ReportViewer (sandboxed iframe). Zod schemas in `src/lib/types.ts` parse all API responses. 48 Jest + RTL tests. `make frontend-test`. `make run-frontend` (port 3100). DECISIONS.md Entry 032. **Phase 2-L (or Jay's next directive) is next.**
**Phase 2-J COMPLETE** -- Payment Service MVP (Stripe Checkout). `src/backend/payment_service/` FastAPI shell on port 8005. Migration 0006 adds `stripe_checkout_session_id VARCHAR(200) NULL` (partial unique index) and `payment_status VARCHAR(20) DEFAULT 'unpaid'` (CHECK: unpaid|pending|paid|refunded) to `reports`. `PaymentRepository` (sync SQLAlchemy, `src/backend/payment_service/repository.py`): `get_report_row`, `set_checkout_session`, `get_report_by_session`, `complete_payment`, `upsert_user`, `create_use_agreement`. `POST /v1/payments/checkout`: validates NPI + `certified_personal_use_only=True` (Path B gate), creates Stripe Checkout session, stores `stripe_checkout_session_id`, returns `{checkout_url, session_id}`. `POST /v1/payments/webhook`: signature verification via `PAYMENT_STRIPE_WEBHOOK_SECRET`, routes `checkout.session.completed`, upserts user + creates use_agreement + backfills reports row; idempotent (skips if already paid); DB errors return 200. `PaymentServiceSettings` (PAYMENT_ prefix). `stripe` SDK added to pyproject.toml. 60 new tests (51 payment + 9 migration). 1318 total. DECISIONS.md Entry 031. `make payment-test`. **Phase 2-K (Frontend Phase 1) is next.**
**Phase 2-I COMPLETE** -- Report Generation MVP (Phase 2-I). Aurora persistence + Temporal pipeline trigger. Migration 0005 adds `report_json JSONB` + `report_html TEXT` to `reports` table; makes `user_id`/`use_agreement_id` nullable for pre-payment MVP. `ReportRepository` (sync SQLAlchemy, `src/backend/report_service/repository.py`): `create_row`, `mark_complete`, `mark_failed`, `get_row`. `persist_report_activity` (new Temporal activity, `src/workers/activities/persist_report.py`): persists `ProviderPipelineResult` to Aurora; best-effort, never raises. `ProviderPipelineWorkflow` step 7 calls `persist_report_activity` when `inp.report_id` is set. `POST /v1/reports/request`: validates NPI, creates DB row, fires `ProviderPipelineWorkflow`, returns `{report_id, status, db_persisted, temporal_queued}` immediately. `GET /v1/reports/{report_id}`: polls report status + returns result. `ReportServiceSettings` (REPORT_ prefix, fallback to DATABASE_URL). 65 new tests. 1258 total. DECISIONS.md Entry 030.
**Phase 2-G COMPLETE** -- Provider Search Service (C14). `src/search/` pure library + `src/backend/search_service/` FastAPI shell on port 8003. `build_provider_doc()` converts `CanonicalProviderProfile` to a `ProviderDoc` (mirrors `providers_index_template.json` mapping). `build_search_query()` builds bool + function_score DSL (multi_match with fuzziness, filter clauses for state/specialty/entity_type/exclusion/license, identity_confidence boost factor 1.5). `OpenSearchClient` thin httpx wrapper (index_doc, bulk_index, search, get_doc). `ProviderIndexer` coordinates document build + client write (single + batch). FastAPI endpoints: `GET /v1/providers/search`, `GET /v1/providers/{npi}` (O(1) get_doc), `POST /v1/providers/{npi}/index`. 108 new tests. 993 total. DECISIONS.md Entry 028. `make search-test`.
**Phase 2-F COMPLETE** -- Entity Linking & Merge MVP (C13). Pure in-memory library (`src/entity_linker/`) that builds `CanonicalProviderProfile` from a `UnifiedIdBundle` (C12) + all contributing `NormalizedRecord` objects. `EntityLinker.build_profile()` routes records by `record_type` discriminator, calls per-type extractors (OIG/SAM exclusions, CMS hospital affiliations + practice context, Medicare/Medicaid participation, publications, clinical trials), resolves specialty group via I4 crosswalk (`get_specialty_group()`), computes 4 derived signals (exclusion_flag, identity_confidence, specialty_classification, data_completeness), calculates `report_completeness_score` via `COMPLETENESS_WEIGHTS` rubric (8 weighted sections, sum=1.0). `is_partial = completeness < 0.70 OR human_review_required`. `report_disclaimer_required=True` always (Path B). `MergeResult` wraps profile + `RecordTypeCounts` + `specialty_group`. 109 new tests. 885 total. DECISIONS.md Entry 027. `make entity-linker-test`.
**Phase 2-E COMPLETE** -- Identity Resolution MVP (C12). Pure in-memory library (`src/identity/`) that groups `NormalizedRecord` objects (C11 output) into `UnifiedIdBundle` objects. `IdentityResolver` + `ConfidenceScorer` + `IdentityStore` + `ResolutionResult`/`BatchResolutionSummary`. NPI-exact-match as sole MVP strategy. F1 (NPPES) is identity anchor: full identity extracted on F1; non-F1 first records get stub bundle + human_review_required. 4-tier confidence: F1 base 0.950; F4/I1/I2 +0.015 each; F2 +0.005; F3/A1/A2 +0.000; F1-absent max 0.750. F1+F4+I1 = 0.980 >= 0.98 architecture target. Idempotency via SKIPPED on duplicate source_id. Batch sorts F1 first. 61 new tests. 776 total. DECISIONS.md Entry 026. `make identity-test`. Commit 7d08023.
**Phase 2-D COMPLETE** -- Normalization Layer MVP (C11). Pure transformation library (`src/normalizers/`) that converts `RawRecord` objects (C10 output) into typed `NormalizedRecord` subclasses. `SourceNormalizer` ABC + `NormalizationError` in `base.py`; registry in `registry.py`; 8 concrete normalizers for F1/F2/F3/F4/I1/I2/A1/A2 in `sources/`. `source_record_id` set here for all P1 sources (was deferred from C10). I4 taxonomy crosswalk applied via `get_specialty_group()` helper. `_parse_date()` handles 6 formats. F3/A1/A2 require caller-supplied `entity_npi`; F2 falls back from raw["NPI"] to parameter. 128 new tests. 715 total. DECISIONS.md Entry 025. `make normalizers-test`.
**Phase 2-C COMPLETE** -- Source Health Monitor MVP (C24). `HealthStore` (in-memory, state + history accumulation) + `SourceHealthMonitor` (stateless threshold engine) + FastAPI shell on port 8002. Migration `0004_source_health_history` adds the append-only history table. 5 alert types: CONSECUTIVE_FAILURES (warning=3, critical=5), SCHEMA_DRIFT, STALE_SOURCE (bulk=48h, API=4h), LOW_RECORD_COUNT, AUTH_FAILURE. 8 P1 connector sources pre-seeded (I4 excluded -- derived helper). Alerting rules extended: DataSourceConsecutiveFailuresWarning/Critical + DataSourceStale. 64 new tests (38 backend + 26 migration). 587 total tests. DECISIONS.md Entry 024.
**Phase 2-B COMPLETE** -- Federal Source Adapters (C10) -- all 9 P1 sources built. **2-B.9 COMPLETE** -- ClinicalTrials.gov (A2, `src/connectors/sources/clinical_trials.py`): ClinicalTrials.gov API v2; cursor pagination (`pageToken`; absent = last page); `investigator_name` constructor arg; single `protocolSection` (dict) contract; no API key; 17 tests. DECISIONS.md Entry 023. **2-B.8 COMPLETE** -- PubMed / NCBI Entrez (A1, `src/connectors/sources/pubmed.py`): two-step esearch+esummary per batch; `retstart`/`retmax` pagination; `author_name` + optional `api_key` constructor args; 4-field contract (`uid`, `title`, `pubdate`, `authors`); 21 tests. DECISIONS.md Entry 022. **2-B.7 COMPLETE** -- NPPES Specialty Crosswalk (I4, `src/connectors/sources/nppes_taxonomy.py`): derived signal; no SourceConnector; `TAXONOMY_CROSSWALK` dict (~200+ NUCC codes) + `crosswalk_taxonomy_code` + `infer_specialty_group`; primary-first fallback; used by C11 normalization (Phase 2-D); 31 tests. DECISIONS.md Entry 021.
**2-B.6 COMPLETE** -- CMS Medicaid Enrollment adapter (source I2, `src/connectors/sources/cms_medicaid_enrollment.py`): single-dataset SODA adapter; `$limit/$offset/$order=:id` pagination; short-page sentinel; 5-field `SchemaContract` (`npi`, `last_name`, `first_name`, `state_cd`, `provider_type_desc`); configurable `dataset_id` (must be verified before live ingest); no API key; 20 tests. DECISIONS.md Entry 020.
**2-B.5 COMPLETE** -- CMS Medicare Enrollment adapter (source I1, `src/connectors/sources/cms_medicare_enrollment.py`): single connector, two SODA dataset passes -- enrollment first, then opt-out affidavits; each row tagged `_record_type = "enrollment" | "opt_out"` for C11 routing; two per-type `SchemaContract`s applied in `fetch_raw` (base-class contract suppressed); configurable `enrollment_dataset_id` + `opt_out_dataset_id`; partial-result on opt-out failure; 26 tests. DECISIONS.md Entry 019.
**2-B.4 COMPLETE** -- CMS Care Compare adapter (source F4, `src/connectors/sources/cms_care_compare.py`): Socrata SODA paginated REST API against `https://data.cms.gov/resource/{dataset_id}.json`; `$limit`/`$offset`/`$order=:id` pagination; terminates on short-page sentinel; no API key; configurable `dataset_id`; one-row-per-location semantics (C11 groups by NPI); `SchemaContract` guards 8 fields (`npi`, `ind_pac_id`, `last_name`, `first_name`, `pri_spec`, `assgn`, `cty`, `st`); 17 tests. DECISIONS.md Entry 018.
**2-B.3 COMPLETE** -- SAM.gov Exclusions adapter (source F3, `src/connectors/sources/sam_gov.py`): paginated REST API against `https://api.sam.gov/entity-information/v3/exclusions`; `api_key` passed at construction time (not in config); pagination terminates on empty `entityData` page or when `(page+1)*size >= totalRecords`; `SchemaContract` guards two top-level keys (`exclusionDetails` and `entityRegistration` as dicts, R6 drift guard); delta-sync mode deferred; 15 tests. DECISIONS.md Entry 017.
**2-B.2 COMPLETE** -- OIG LEIE adapter (source F2, `src/connectors/sources/oig_leie.py`): bulk-download mode, downloads the monthly LEIE exclusions CSV from HHS OIG (`/exclusions/downloadables/LEIE.csv`), parses with `csv.DictReader`, yields one dict per exclusion row; `SchemaContract` guards 11 key columns (R6 drift guard); empty-string NPI is valid for pre-NPI-era exclusions; `_parse_csv_text()` maps empty/broken responses to `SourceUnavailableError`. Built + contract-tested against stubbed transports only -- no network. API spot-check deferred. DECISIONS.md Entry 016. 12 tests.
**2-B.1 COMPLETE** — NPPES / NPI Registry adapter (source F1, `src/connectors/sources/nppes.py`): API-lookup mode against the public CMS NPPES API (`/api/?version=2.1`, paginated via `skip`), a validated `NppesQuery`, a `SchemaContract` over `{number, enumeration_type, basic, addresses, taxonomies}` (R6 guard), and NPPES's HTTP-200-with-`Errors` failure mode mapped to a non-retryable error. Concrete adapters live in `src/connectors/sources/`. Built + contract-tested against stubbed transports only — **no network**; live ingestion against NPPES is a deploy-time action governed by the Phase 0 legal gate (F1 is T1/L0 open-data). Bulk-download mode deferred. DECISIONS.md Entry 015. 14 tests.
**Phase 2-A COMPLETE** — Source Connector Framework (`src/connectors/`, component C9): the async-first library every source adapter (C10) builds on — `SourceConnector` ABC, `ConnectorConfig`, error taxonomy, in-house retry/backoff, client-side throttling, a `SchemaContract` runtime drift guard (risk R6), and a reusable `assert_connector_contract` test harness. Output is a `RawRecord` (pre-normalization; C11 is Phase 2-D) + a `SourceHealthRecord` per run. 21 tests (sync, via `asyncio.run` — no pytest-asyncio). Framework only — no live source fetched (legal gate governs the C10 adapters). DECISIONS.md Entry 014. Phase 2-B (Federal Source Adapters) is next.
**Phase 1-I COMPLETE** — Audit Ledger Service (`src/backend/audit_service/`, component C5-audit): the append-only, hash-chained ledger that replaces QLDB (Entry 005). `ledger.py` assigns `prev_event_hash`/`event_hash` per `(target_type, target_id)` chain, appends immutably, and verifies by recomputation (detects altered contents and removed/reordered events); FastAPI surface for append/chain/verify/checkpoint; 15 behavior tests; runs via `make run-audit`. Deploys to the `workers` namespace (internal-only ClusterIP, NetworkPolicy baseline); Aurora-only (S3 WORM = Phase 4-F). DECISIONS.md Entry 013. **Phase 1 foundations complete.**
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
| 2-A | Source Connector Framework (C9 — base classes, retry/throttle, contract testing) | ✅ Complete |
| 2-B | Federal Source Adapters (all 9 P1 sources) | ✅ Complete |
| 2-C | Source Health Monitor MVP (C24) | ✅ Complete |
| 2-D | Normalization Layer MVP (C11) | ✅ Complete |
| 2-E | Identity Resolution MVP (C12) | ✅ Complete |
| 2-F | Entity Linking & Merge MVP (C13) | ✅ Complete |
| 2-G | Provider Search Service (C14) | ✅ Complete |
| 2-H | Temporal Workflow + Basic Report Generation (C15+C17) | ✅ Complete |
| 2-I | Report Generation MVP -- Aurora persistence + Temporal trigger | ✅ Complete |
| 2-J | Payment Service MVP (Stripe Checkout) | ✅ Complete |
| 2-K | Frontend Phase 1 (Auth + Search + Report Viewer) | 🔄 Up next |

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
make run-monitor     # source health monitor (FastAPI) on :8002 — in-memory store
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
| `src/backend/source_health_monitor/` | **Source Health Monitor (C24, Phase 2-C)** -- `HealthStore` + `SourceHealthMonitor` + FastAPI shell on :8002 |
| `src/backend/source_health_monitor/README.md` | Monitor quick-reference -- P1 registry, alert types/thresholds, REST API, run/test |
| `src/data/migrations/versions/0004_source_health_history.py` | Migration 0004 -- `source_health_history` append-only time-series table + I1/I2/A1/A2 seed rows |
| `src/search/` | **Provider Search Service (C14, Phase 2-G)** -- pure library; `build_provider_doc()`, `build_search_query()`, `ProviderIndexer`, `OpenSearchClient` (httpx); FastAPI shell in `src/backend/search_service/` on :8003 |
| `src/search/document.py` | `build_provider_doc(profile) -> ProviderDoc` -- pure; maps `CanonicalProviderProfile` to OpenSearch document shape |
| `src/search/query.py` | `build_npi_query()`, `build_search_query()` -- pure DSL builders; function_score identity_confidence boost |
| `src/search/client.py` | `OpenSearchClient` -- httpx wrapper; `index_doc`, `bulk_index`, `search`, `get_doc` |
| `src/search/indexer.py` | `ProviderIndexer` -- `index_profile()` + `index_batch()` coordinator |
| `src/backend/search_service/` | FastAPI shell: `GET /v1/providers/search`, `GET /v1/providers/{npi}`, `POST /v1/providers/{npi}/index` |
| `tests/search/` | 81 search library tests -- document/query/indexer unit tests |
| `tests/backend/test_search_service.py` | 27 FastAPI TestClient tests for search service routes |
| `src/entity_linker/` | **Entity Linking & Merge (C13, Phase 2-F)** -- pure in-memory library; `EntityLinker.build_profile()` assembles `CanonicalProviderProfile` from `UnifiedIdBundle` + `NormalizedRecord` list |
| `src/entity_linker/config.py` | `LinkerSettings` -- `max_recent_publications`, `completeness_threshold_for_partial` (env prefix LINKER_) |
| `src/entity_linker/extractors.py` | Per-record-type pure extraction functions (OIG, SAM, CMS, Medicare, Medicaid, PubMed) |
| `src/entity_linker/signals.py` | 4 derived signal builders: `exclusion_flag`, `identity_confidence`, `specialty_classification`, `data_completeness`; `COMPLETENESS_WEIGHTS` rubric |
| `src/entity_linker/merger.py` | `EntityLinker` class -- `build_profile(bundle, records) -> MergeResult`; routes by `record_type` discriminator |
| `src/entity_linker/models.py` | `MergeResult` (profile + `RecordTypeCounts` + `specialty_group` + `merged_at`) |
| `tests/entity_linker/` | 109 entity linker tests -- extractors/signals/merger unit tests + integration tests |
| `src/identity/` | **Identity Resolution Engine (C12, Phase 2-E)** -- pure in-memory library; `IdentityResolver` + `ConfidenceScorer` + `IdentityStore` |
| `src/identity/config.py` | `IdentitySettings` -- all thresholds + source tier assignments (configurable via env vars) |
| `src/identity/confidence.py` | `ConfidenceScorer` -- stateless 4-tier model; F1 base; F4/I1/I2 corroborating; F2 partial; F3/A1/A2 no boost |
| `src/identity/models.py` | `ResolutionResult`, `ResolutionAction` (CREATED/MERGED/SKIPPED), `BatchResolutionSummary` |
| `src/identity/store.py` | `IdentityStore` -- in-memory dict keyed by primary_npi; Aurora-backed at deploy |
| `src/identity/resolver.py` | `IdentityResolver` -- `resolve()` + `resolve_batch()` + `_create_bundle()` + `_merge_record()` + `_merge_f1()` |
| `tests/identity/` | 61 identity tests -- confidence/store/resolver unit tests + 6 integration tests |
| `src/normalizers/` | **Normalization Layer (C11, Phase 2-D)** -- pure transformation library; `SourceNormalizer` ABC + registry + 8 P1 normalizers |
| `src/normalizers/base.py` | `SourceNormalizer` ABC, `NormalizationError`, `_parse_date()`, `_extract_npi()`, `_clean_phone/zip()` |
| `src/normalizers/registry.py` | `@register` decorator + `get_normalizer(source_id)` + `registered_source_ids()` |
| `src/normalizers/sources/` | Concrete normalizers: `f1_nppes.py` (+ `get_specialty_group()`), `f2_oig_leie.py`, `f3_sam_gov.py`, `f4_cms_care_compare.py`, `i1_medicare_enrollment.py`, `i2_medicaid_enrollment.py`, `a1_pubmed.py`, `a2_clinical_trials.py` |
| `tests/normalizers/` | 128 normalizer tests -- base/registry + one file per source normalizer |
| `src/backend/audit_service/deploy/` | kustomize Deployment + Service + NetworkPolicies (workers namespace, workers-sa) |
| `src/gitops/argocd/workloads/audit-service.yaml` | Audit service ArgoCD child app (workers namespace) |
| `tests/backend/test_audit_service.py` | 15 behavior tests (append/hash, chain linkage, tamper detection, checkpoints) |
| `src/connectors/` | **Source Connector Framework (C9)** — base classes, retry/throttle, schema-drift contract, test harness |
| `src/connectors/base.py` | `SourceConnector` ABC — adapters implement `fetch_raw`; `run()` orchestrates fetch + health |
| `src/connectors/testing.py` | Reusable contract-test harness (`assert_connector_contract`, `stub_transport`) for C10 adapters |
| `src/connectors/README.md` | Connector framework quick-reference — how to write + contract-test an adapter; built-adapter inventory |
| `tests/connectors/test_framework.py` | 21 framework tests (hashing, retry/backoff, throttle, contract, run/health) |
| `src/connectors/sources/` | **Concrete source adapters (C10)** — one module per source; legal-gate notice + F1/F2/F3 inventory in `__init__.py` |
| `src/connectors/sources/nppes.py` | **NPPES / NPI adapter (F1, 2-B.1)** — `NppesConnector` API-lookup + `NppesQuery` + `nppes_config()` |
| `tests/connectors/test_nppes.py` | 14 NPPES tests (query validation, pagination via skip, schema drift, Errors-array/non-JSON failure) |
| `src/connectors/sources/oig_leie.py` | **OIG LEIE adapter (F2, 2-B.2)** -- `OigLeieConnector` bulk CSV + `oig_leie_config()`; empty-NPI-era rows handled |
| `tests/connectors/test_oig_leie.py` | 12 OIG LEIE tests (identity, contract harness, CSV parsing, schema drift, empty/broken/503 failure modes) |
| `src/connectors/sources/sam_gov.py` | **SAM.gov Exclusions adapter (F3, 2-B.3)** -- `SamGovConnector` paginated REST API + `sam_gov_config()`; api_key at construction; two-dict contract |
| `tests/connectors/test_sam_gov.py` | 15 SAM.gov tests (identity, contract harness, pagination stop modes, schema drift x3, non-JSON/503/401 failure modes) |
| `src/connectors/sources/cms_care_compare.py` | **CMS Care Compare adapter (F4, 2-B.4)** -- `CmsCareCompareConnector` SODA paged JSON + `cms_care_compare_config()`; configurable dataset_id; one-row-per-location |
| `tests/connectors/test_cms_care_compare.py` | 17 CMS tests (identity, contract harness, pagination x5 incl. exact-page+empty, multi-NPI rows, schema drift x3, extra fields, non-JSON/non-list/503) |
| `src/connectors/sources/state_boards/` | **Phase 3-A + 3-B state board adapters (P2 sources)** -- 10 adapters, source_id prefix `state_board_*`. 3-A: CA=BULK_DOWNLOAD (DCA CSV, 7-field); NY/GA/PA/MI=REST_API SODA (6-field); TX/NC=REST_API page-number (6-field); FL/OH=REST_API offset (6-field); IL=REST_API offset (5-field). All carry `_FIELD_MAP` normalizing API casing variants to snake_case. Tested stub-only; live ingest behind legal gate. |
| `src/connectors/sources/court_records/` | **Phase 3-C court record adapters (C1-C2 P2 + state courts early P3)** -- 5 adapters, source_id prefix `court_*`. CourtListener=page-number/next-null, PACER=0-indexed page-number/totalPages, TX/FL=offset/limit, NY=page-number/next-null + bare list. All use `SourceCategory.COURT`, carry `_FIELD_MAP`, normalize `None` to `""`. Auth: CourtListener `Authorization: Token`, PACER `X-NEXT-GEN-CSO`. Lookup-by-name pattern (party_name constructor arg). Tested stub-only. |
| `src/data/migrations/versions/0007_state_board_seeds.py` | Migration 0007 -- seeds 5 `source_health_records` rows (state_board_ca/ny/tx/fl/il, status=unknown, category=state_board). Chains from 0006. ON CONFLICT DO NOTHING (idempotent). |
| `src/data/migrations/versions/0008_state_board_seeds_batch2.py` | Migration 0008 -- seeds 5 Phase 3-B `source_health_records` rows (state_board_ga/pa/oh/mi/nc). Chains from 0007. ON CONFLICT DO NOTHING. Does not touch 3-A rows. |
| `src/data/migrations/versions/0009_court_record_seeds.py` | Migration 0009 -- seeds 5 Phase 3-C `source_health_records` rows (court_listener/pacer/court_tx/court_fl/court_ny, category='court'). Chains from 0008. ON CONFLICT DO NOTHING. Does not touch state board rows. |
| `tests/connectors/test_ca_medical_board.py` | 16 CA tests (config, contract harness, CSV normalization x4 including space-separated headers, extra columns, bulk-makes-1-request, drift note: CSV header absence triggers drift) |
| `tests/connectors/test_ny_op_nysed.py` | 14 NY tests (config, contract harness, SODA pagination x4, drift, non-list/non-JSON failure) |
| `tests/connectors/test_tx_medical_board.py` | 15 TX tests (config, contract harness, page-number pagination x3, camelCase normalization, dict-wrapped response, drift, non-JSON failure) |
| `tests/connectors/test_fl_doh.py` | 16 FL tests (config, contract harness, offset pagination x3, mixed-case normalization, providers/results key unwrap, drift, failure modes) |
| `tests/connectors/test_il_idfpr.py` | 17 IL tests (config, contract harness, offset pagination x3, uppercase+camelCase normalization, licenses/records/data key unwrap, drift, failure modes) |
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

**Phase 2-N:** PDF Report Generation -- add `GET /v1/reports/{report_id}/pdf` to the report service (WeasyPrint); gated on status=complete + payment_status=paid; Next.js proxy route + "Download PDF" anchor in `ReportViewer.tsx`.

**Phase 3-A state board adapters validate locally (no network -- transports stubbed):**
```bash
PYTHONPATH=src pytest tests/connectors/test_ca_medical_board.py tests/connectors/test_ny_op_nysed.py tests/connectors/test_tx_medical_board.py tests/connectors/test_fl_doh.py tests/connectors/test_il_idfpr.py -v
# Expected: 76 passed
```

**All connectors validate locally (no network -- transports stubbed):**
```bash
make connectors-test                              # or: PYTHONPATH=src pytest tests/connectors/ -v  (~155 tests total)
```

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
