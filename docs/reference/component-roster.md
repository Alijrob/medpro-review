# Component Roster — C1 through C26

| Component | Purpose | Key Dependencies | Effort |
|-----------|---------|-----------------|--------|
| **C1** — Legal & Compliance Workstream | FCRA determination, ToS matrix, data licensing posture, compliance architecture spec | Product Spec, Source Inventory | 16 wk (blocking) |
| **C2** — Policy Engine (OPA) | Enforces all authorization and compliance policies (FCRA rules, data redaction, permissible use) | C1, C3, C6 | 9 wk |
| **C3** — Infrastructure Foundation | EKS, VPC, IAM, KMS, network segmentation, GitOps | Business Requirements | 8 wk |
| **C4** — Observability Stack | OpenTelemetry -> Prometheus, Loki, Tempo, Grafana, Sentry | C3 | 7 wk |
| **C5** — Core Data Stores | Aurora PostgreSQL, Redis, OpenSearch, S3, QLDB operational setup | C3, C23 | 8 wk |
| **C6** — Canonical Schema & Registry | Pydantic models, JSON Schema, schema versioning, schema registry | Domain Modeling, C1 | 8 wk |
| **C7** — Auth & Identity Service | Auth0/Okta integration, JWT handling, RBAC, user data privacy controls | C3, C5, C8 | 8 wk |
| **C8** — API Gateway & FastAPI Backend | REST API, routing, auth middleware, idempotency, WAF, rate limiting | C2, C3, C7 | 9 wk |
| **C9** — Source Connector Framework | Base classes, error handling, throttling, retry/backoff, contract testing | C3, C4, C24 | 9 wk |
| **C10** — Source Adapters | Specific integrations per external source (avg 4 wk/adapter, phased) | C2, C6, C9 | Varies |
| **C11** — Normalization Layer | Raw source data -> NormalizedRecord; handles variations across all sources | C6, C10, C25 | 11 wk |
| **C12** — Identity Resolution Engine | Provider name -> UnifiedIdBundle; probabilistic ML matching; HitL validation | C5, C6, C11, C25 | 14 wk |
| **C13** — Entity Linking & Merge | Creates/updates Canonical Provider Profile; provenance tagging | C2, C5, C6, C11, C12, C25 | 13 wk |
| **C14** — Provider Search Service | Fast, accurate provider search using OpenSearch on Canonical Profile | C5 (OpenSearch), C13 | 8 wk |
| **C15** — Workflow Orchestration (Temporal) | End-to-end report generation and dispute workflows; parallel fan-out; SLA | C9-14, C16, C17, C23, C24 | 14 wk |
| **C16** — Analytics & Anomaly Detection | Derived signals (risk, confidence); anomaly detection; legal-reviewed explanations | C5, C13, C25 | 11 wk |
| **C17** — Report Generation Service | HTML, PDF (WeasyPrint), JSON reports; compliance disclaimers | C2, C5, C13, C16 | 11 wk |
| **C18** — Payment Service (Stripe) | Checkout, subscriptions, entitlements, refunds, customer portal | C3, C7, C8 | 8 wk |
| **C19** — Frontend Application | Next.js: search, report viewer, account mgmt, dispute initiation | C8, C18 | 18 wk |
| **C20** — Dispute Workflow Service | Dispute lifecycle; FCRA 30-day SLA; HitL; full audit trail | C2, C5, C7, C13, C15, C17, C22, C23 | 12 wk |
| **C21** — Admin Dashboard | Internal UI: source health, disputes, reports, users | C7, C8, C16, C20, C24, C25 | 14 wk |
| **C22** — Notifications Service | Multi-channel: email, SMS, webhooks, system alerts | C5, C7, C15 | 7 wk |
| **C23** — Audit Ledger Service (QLDB) | Immutable, verifiable audit ledger; QLDB Streams to S3 | C3, C5 | 7 wk |
| **C24** — Source Health Monitor | Continuous monitoring: API availability, latency, schema drift detection, alerts | C4, C9 | 10 wk |
| **C25** — Data Quality Service | Completeness, validity, contradiction detection, confidence scoring | C2, C5, C6, C13 | 12 wk |
| **C26** — Security Hardening & Pen Testing | Ongoing security assessments, threat modeling, external pen testing, SAST/DAST | All components | Throughout all phases |

---

## Phase-to-Component Mapping

### Phase 1 — Foundations
C3, C4, C6, C2 (baseline), C23, C7, C8, C9, C26 (baseline)

### Phase 2 — Core Identity & MVP
C10 (initial: NPPES, OIG, SAM.gov, 3-5 state boards), C11 (MVP), C12 (MVP), C13 (basic), C14, C18 (MVP), C19 (Phase 1), C15 (basic), C17 (basic)

### Phase 3 — Expanded Data Coverage
C10 (broader: state boards, courts, commercial, reviews, insurance, academic), C12 (upgrade with ML), C25 (Phase 1), C24 (Phase 2)

### Phase 4 — Orchestration & Intelligence
C15 (full), C16, C25 (Phase 2), C2 (Phase 2 - FCRA policies), C23 (Phase 2 - QLDB Streams)

### Phase 5 — Productization & Operations
C19 (full), C17 (full - WeasyPrint PDF), C20, C21, C22, C18 (full)

### Phase 6 — Hardening & Launch
C26 (pen test, SOC 2), chaos engineering, load testing, DR drills
