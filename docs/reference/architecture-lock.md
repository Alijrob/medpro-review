# Architecture Lock — Medical Professionals Review

**Status:** LOCKED
**Approved:** 2026-05-24T05:17:15.688Z
**Verdict:** PASS

---

## Architecture Lock Report

### Verdict Rationale

The plan satisfies all eight lock criteria: components, stack, data model entities, integrations, build sequence, acceptance criteria, and risk ownership are all explicitly defined with no unresolved contradictions. The Phase 0 legal gate is appropriately structured with a defined exit (16-week timebox plus pivot/pause fallback), so the architecture is buildable subject to that gate. Remaining concerns are acknowledged as managed risks rather than open architectural questions.

### Checklist Results

1. PASS — 26 components (C1-C26) named with purpose, dependencies, and effort.
2. PASS — Stack fully specified: FastAPI, Next.js, Temporal, OPA, QLDB, Aurora PostgreSQL, Redis, OpenSearch, S3, EKS, OpenTelemetry, Auth0/Okta, Stripe.
3. PASS — Entities defined: UnifiedIdBundle, NormalizedRecord, Canonical Provider Profile, with provenance/confidence metadata and schema registry (C6).
4. PASS — Integrations identified: NPPES, OIG LEIE, SAM.gov, state boards, PACER, Ribbon, Healthgrades, Vitals, Google/Yelp APIs, Doximity, PubMed, Stripe, Auth0/Okta.
5. PASS — No contradictions detected; SLA, FCRA pivot strategy, and vendor lock-in trade-offs are reconciled consistently across sections.
6. PASS — Acceptance criteria are quantified and testable (>=6 source categories, 95% within 10min, >98% precision, >99.9% uptime, SOC 2 readiness).
7. PASS — Six-phase sequence respects dependencies (Phase 0 legal gate -> foundations -> identity -> coverage -> orchestration -> product -> hardening).
8. PASS — Every component has effort estimate; SRE, security (C26), and dispute staffing are explicitly owned.

### Locked Architecture Decisions

**Stack (locked):**
- Backend: FastAPI (Python)
- Frontend: Next.js / TypeScript
- Orchestration: Temporal
- Policy: Open Policy Agent (OPA)
- Audit Ledger: AWS QLDB + S3 streams
- Primary DB: AWS Aurora PostgreSQL
- Cache/Rate Limit: AWS ElastiCache (Redis)
- Search: OpenSearch
- Object Store: AWS S3
- Cloud: AWS (single-cloud for MVP)
- Container Platform: AWS EKS (Kubernetes)
- IaC: Terraform/Terragrunt
- GitOps: ArgoCD
- CI/CD: GitHub Actions
- Auth: Auth0/Okta IDaaS + custom overlay
- Observability: OpenTelemetry -> Prometheus, Loki, Tempo, Grafana, Sentry
- Secrets: AWS Secrets Manager + External Secrets Operator
- Payments: Stripe
- Schema: Pydantic + JSON Schema with registry

**Data model (entity-level, locked):**
- UnifiedIdBundle (identity resolution output)
- NormalizedRecord (per-source standardized)
- Canonical Provider Profile (merged, provenance-tagged, confidence-scored)
- User, Report, Dispute, AuditEvent (QLDB)
- SourceHealth, DerivedSignal (risk/stability/confidence/anomaly)

**Integration points (locked):**
- Federal: NPPES, OIG LEIE, SAM.gov
- State: 50+ licensing boards (phased)
- Legal: PACER + 5 key state court systems
- Commercial: Ribbon Health, Healthgrades, Vitals (licensed)
- Reviews: Google Places, Yelp (official APIs)
- Insurance: Licensed directory providers
- Academic: PubMed, Doximity
- Payments: Stripe
- Auth: Auth0/Okta

**Build sequence (locked):**
- Phase 0 — Legal & Discovery (16 wk, blocking)
- Phase 1 — Foundations (4 mo): C3, C4, C6, C2, C23, C7, C8, C9, C26 baseline
- Phase 2 — Core Identity & MVP (4 mo): C10 initial, C11, C12, C13, C14, C18 MVP, C19 Phase 1, C15 basic, C17 basic
- Phase 3 — Expanded Data Coverage (6 mo): broader C10, C12 upgrade, C25 Phase 1, C24 Phase 2
- Phase 4 — Orchestration & Intelligence (4 mo): C15 full, C16, C25 Phase 2, C2 Phase 2, C23 Phase 2
- Phase 5 — Productization & Operations (4 mo): C19 full, C17 full, C20, C21, C22, C18 full
- Phase 6 — Hardening & Launch (4 mo): pen testing, SOC 2, chaos, load, DR, launch
- Total: ~26 months

**Cross-cutting locks:** Zero-Trust network architecture; compliance-by-design via OPA + QLDB; partial reports as first-class output; >98% identity precision threshold; 10-min comprehensive / 2-min partial SLA.

### Recommendations (non-blocking)

1. The "pre-approved non-CRA pathway" referenced in the Phase 0 fallback is asserted but not detailed — capture its architectural delta in a Phase 0 deliverable so the pivot is truly executable.
2. The 26-month timeline still assumes high parallelism; recommend explicit headcount/team-topology plan before Phase 1 kickoff to validate the parallel tracks.
3. Adapter effort is averaged ("3-5 weeks per adapter, avg 4"); recommend locking a per-source matrix during Phase 0 to prevent C10 scope creep.
4. Ground-truth dataset for >98% identity precision is referenced but not owned — assign curation ownership (likely C12 team + clinical SME) before Phase 2.
5. Consider defining a numeric ceiling for dispute volume that triggers staffing escalation, since R14 mitigation depends on a "staffed team" without a sizing model.
6. ToS change detection via C24 is partially "manual review where automation infeasible" — define cadence and ownership explicitly in the C1/C24 runbook.

---

## 1. Project Overview

### 1.1 What We Are Building

The Healthcare Provider Intelligence & Vetting Platform is a consumer-facing service designed to provide comprehensive, transparent intelligence reports on healthcare providers. Users can enter a provider's name and, within approximately 10 minutes (for comprehensive reports) or significantly faster (for partial reports), receive a detailed report synthesizing data from over 6 critical source categories, with clear provenance:

- **Government Registries:** Federal (NPPES, OIG LEIE, SAM.gov), State Licensing Boards (50+ states).
- **Legal Systems:** Court records (PACER, state, county).
- **Commercial Data:** Directories (Ribbon Health, Healthgrades, Vitals).
- **Public Opinion:** Review platforms (Google, Yelp via official APIs).
- **Insurance Networks:** Participation details from licensed data providers.
- **Academic/Research Databases:** PubMed, Doximity.

Each report covers: Identity, Location History, Disciplinary & Legal Actions, Insurance Participation, Review Intelligence, Derived Signals.

### 1.2 Why This Project Matters

Currently, evaluating healthcare providers is fragmented, time-consuming, and opaque. This platform centralizes data, verifies provenance, and presents it in a unified, legally-defensible report. It adheres to a "Compliance-First, Accuracy-First" philosophy.

### 1.3 Critical Constraint: Legal & Discovery Phase (Phase 0)

**No full production engineering may proceed until Phase 0 is complete.** The platform's FCRA classification is a fundamental prerequisite. If deemed a CRA, it triggers significant compliance obligations. The 16-week timebox is non-negotiable.

---

## 2. Architecture Overview

1. **User Interaction:** Next.js frontend
2. **API Gateway & Backend:** FastAPI + OPA + rate limiting
3. **Workflow Orchestration:** Temporal (fault-tolerant, auditable, parallel fan-out)
4. **Data Storage:** Aurora PostgreSQL (system of record), Redis (cache), OpenSearch (search), S3 (objects), QLDB (immutable audit)
5. **Cross-Cutting:** OpenTelemetry observability, OPA policy enforcement, Secrets Manager, Zero-Trust network

---

## 3. Component Roster

See: [`component-roster.md`](component-roster.md)

---

## 4. Build Sequence

### Phase 0 — LEGAL & DISCOVERY (BLOCKING: 16 weeks)

**Exit Criteria:** Binding FCRA opinion in hand, CAS approved, top 10 source ToS posture defined and legally approved, initial data licensing costs modeled, Legal Gate Closure Document signed.

### Phase 1 — FOUNDATIONS (Months 1-4 post-gate)

Tracks: Infrastructure & Observability, Schema & Compliance Backbone, Foundational Services.
**Exit Criteria:** EKS operational, full observability live, canonical schemas v1 published, OPA and Audit Ledger writing events, Auth service functional end-to-end.

### Phase 2 — CORE IDENTITY & MVP (Months 5-8)

Tracks: Data Ingestion, Identity Pipeline, Initial Frontend & Payments, Initial Report Pipeline.
**Exit Criteria:** End-to-end MVP: user logs in, searches provider, views basic identity/license report from federal sources within SLA. Payment functional. User feedback loop established.

### Phase 3 — EXPANDED DATA COVERAGE (Months 9-14)

Tracks: State Boards & Disciplinary, Reviews & Insurance, Identity & Quality Enhancements, Source Health & Resilience.
**Exit Criteria:** Reports include data from >=6 distinct source categories. Identity resolution achieves >98% precision. Data Quality Service provides quality scores.

### Phase 4 — ORCHESTRATION & INTELLIGENCE (Months 15-18)

Tracks: Full Orchestration & Performance, Analytics & Quality, Audit & Compliance Hardening.
**Exit Criteria:** 95% of comprehensive reports within 10-min SLA. All derived signals with legal-reviewed explanations. Comprehensive OPA enforcement live.

### Phase 5 — PRODUCTIZATION & OPERATIONS (Months 19-22)

Tracks: Full Frontend & Reports, Operational Capabilities, Payment Enhancements.
**Exit Criteria:** All user-facing features operational. Admin can manage system end-to-end. Dispute workflow fully functional and auditable.

### Phase 6 — HARDENING & LAUNCH (Months 23-26)

Security, Resilience, Compliance, Operational Excellence, Launch.
**Exit Criteria:** All acceptance criteria met. SOC 2 readiness validated. System performs reliably under load.

---

## 5. Acceptance Criteria

1. Reports from >=6 distinct, legally permissible source categories
2. 95% of comprehensive reports within 10 minutes; partial within 2 minutes (validated by load testing)
3. Identity resolution >98% precision on core attributes; all data includes provenance; derived signals are explainable
4. Full FCRA compliance enforced by OPA; QLDB audit ledger; dispute resolution meets all legal SLAs
5. Intuitive frontend; HTML + PDF reports; MFA authentication
6. Graceful degradation; Source Health Monitor; Admin Dashboard; >99.9% uptime
7. End-to-end encryption; external pen testing passed; SOC 2 Type II readiness
8. Proven to scale to peak load via load testing and chaos engineering

---

## 6. Risk Register Summary

| # | Risk | Severity |
|---|------|---------|
| R1 | FCRA classification triggers full CRA obligations | CRITICAL |
| R2 | ToS violations or data provider policy changes | CRITICAL |
| R3 | Data licensing costs exceed unit economics | HIGH |
| R4 | False-positive scoring leads to defamation exposure | CRITICAL |
| R5 | 10-minute SLA unachievable | HIGH |
| R6 | Schema drift breaks Source Adapters silently | MEDIUM-HIGH |
| R7 | Identity resolution errors | CRITICAL |
| R8 | Consumer willingness-to-pay below break-even | HIGH |
| R9 | Security breach of user search history or PII | CRITICAL |
| R10 | Phase 0 legal gate delay extends runway burn | HIGH |
| R11 | Integration complexity with 50+ sources | HIGH |
| R12 | Operational complexity and SRE costs | HIGH |
| R13 | Vendor lock-in (AWS-native services) | MEDIUM |
| R14 | High dispute volume overwhelms teams | HIGH |
| R15 | Iterative feedback loops not integrated | MEDIUM |

Full risk register with mitigations: see the final-plan.md in the blueprint repo.
