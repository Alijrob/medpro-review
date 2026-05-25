# DECISIONS.md — Medical Professionals Review

Deviations from the locked architecture plan are logged here. Every entry requires a reason and a risk acknowledgment.

---

## Entry 001 — QLDB Vendor Lock-in: Accepted

**Date:** 2026-05-24
**Decision:** AWS QLDB is used as the immutable audit ledger despite vendor lock-in.
**Reason:** QLDB's cryptographic verifiability is non-negotiable for FCRA-grade compliance and legal defensibility. No open-source alternative provides this guarantee at scale with comparable security properties.
**Risk acknowledged:** AWS vendor dependency. Mitigated by streaming QLDB data to S3 for archival, and by using open-source alternatives (Kubernetes, OpenSearch, PostgreSQL) for all other layers.
**Locked in architecture:** Yes.

---

## Entry 002 — Auth Provider: Auth0 (Locked)

**Date:** 2026-05-24 (opened) / 2026-05-25 (resolved)
**Decision:** **Auth0** is the IDaaS for the auth layer. SDKs: `nextjs-auth0` (frontend, Phase 2-K); Auth0 JWT validation via JWKS in the FastAPI backend (Phase 1-F onward).
**Reason:** Path B (Entry 004) is strictly B2C consumer identity. Auth0 is purpose-built for CIAM — first-class Next.js SDK, social + passwordless login, low-friction consumer signup — whereas Okta's strength is workforce/enterprise SSO, which Path B forecloses. Auth0 is an Okta product, so the choice is not a dead-end if requirements shift.
**Risk acknowledged:** MAU-based pricing dependency on Auth0. Mitigated by building on standard OIDC/JWT (JWKS validation, RS256), so a future move to another OIDC provider is a config change, not a re-architecture.
**Locked:** Yes.

---

## Entry 003 — Deployment Target: Unresolved

**Date:** 2026-05-24
**Status:** UNRESOLVED — Architecture specifies AWS EKS but no specific AWS account, region, or domain has been confirmed for this project.
**Impact:** Blocks Phase 1-B (Terraform skeleton) from becoming deployable. IaC skeletons can be written but not applied until this is locked.

---

## Entry 004 — FCRA Path: Path B (Non-CRA) Locked

**Date:** 2026-05-24
**Decision:** The platform is designed and operated as a non-CRA under Path B. The product is strictly B2C — individual consumers researching healthcare providers for personal decision-making. It is not sold to employers, hospitals, credentialing organizations, insurers, or any institutional buyer making personnel or coverage decisions.
**Reason:** Path B eliminates ~$9,800/month in FCRA compliance overhead, removes 4-5 weeks of engineering for compliance-only components, and reduces legal risk surface. The B2C consumer market ("help patients research their doctor") is large and does not require CRA status.
**Constraints this decision imposes (binding):**
- ToS must explicitly prohibit use in employment, credentialing, licensing, insurance underwriting, or credit decisions
- User must certify permissible use at checkout (personal research only)
- No enterprise API access, no bulk report access, no institutional accounts
- Marketing must not use: "screening," "vetting," "background check," "credential verification," "suitability"
- No adverse action notice infrastructure (C23 is removed — see Entry 006)
**Risk acknowledged:** Forecloses B2B institutional market (hospitals, credentialing bodies, insurers). If business model pivots to institutional buyers, this decision must be revisited and the platform must be re-architected for CRA compliance before any institutional sale is made.
**Locked:** Yes.

---

## Entry 005 — Audit Ledger: QLDB Replaced with Aurora Append-Only + WORM S3

**Date:** 2026-05-24
**Supersedes:** Entry 001 (QLDB vendor lock-in accepted — that justification was FCRA-specific).
**Decision:** QLDB is replaced with append-only Aurora audit tables (row-level security blocks deletes/updates on audit rows) plus a WORM S3 bucket for long-term archival. Cryptographic chain-of-custody is implemented via SHA-256 hash-chaining on Aurora audit rows.
**Reason:** (1) Entry 004 (Path B lock) removes the FCRA-grade compliance justification for QLDB. (2) AWS has signaled QLDB deprecation — continuing to build on a sunsetting service introduces migration risk before launch. (3) Aurora append-only tables with hash-chaining provide equivalent immutability guarantees at lower cost ($0/month vs. $15-600/month) with no vendor lock-in.
**What is preserved:** Full immutable audit trail on every data write, report generation, correction, and access event. Same functional guarantee — different implementation.
**Risk acknowledged:** Aurora append-only enforcement relies on application-layer controls + database role restrictions rather than QLDB's hardware-rooted cryptographic proof. For a non-CRA product this is an acceptable trade-off. If the platform ever pivots to Path A (CRA), QLDB or an equivalent must be re-evaluated.
**Locked:** Yes.

---

## Entry 006 — C23 (Adverse Action Notice Service): Removed

**Date:** 2026-05-24
**Decision:** C23 — Adverse Action Notice Service — is removed from the component roster.
**Reason:** FCRA § 1681m adverse action notices are only required for CRAs. Path B (Entry 004) eliminates this obligation entirely. There is no quality or product function that C23 served beyond FCRA compliance.
**What replaces it (post-MVP, optional):** A physician "profile change alert" — if a physician has claimed their profile and a new disciplinary action or data change is ingested, an optional notification is sent. This is a product feature, not a compliance obligation, and is scoped to a later phase.
**Impact on component roster:** C23 removed. C numbering above C23 is not renumbered — existing references remain valid.
**Locked:** Yes.

---

## Entry 007 — C20, C22, OPA (C8), Data Retention: Retained with Modified Scope

**Date:** 2026-05-24
**Decision:** C20 (Dispute Workflow), C22 (Disclosure), C8 (OPA), and data retention enforcement are all retained. The FCRA-specific compliance wrappers are removed; the underlying quality and governance functions are preserved.
**Scope changes:**
- **C20 Dispute Workflow:** Retains correction pipeline, HitL review, audit trail, and internal 30-day SLA target. Removes FCRA § 1681i mandatory reinvestigation obligations and adverse action retraction machinery.
- **C22 Disclosure:** Retains provider-facing "view your profile data" transparency portal. Legal basis shifts from FCRA § 1681g to CCPA (California physician data access rights). All California-resident provider data remains subject to CCPA access and deletion requests.
- **C8 OPA Policy Engine:** Retained in full. FCRA permissible-purpose policies are replaced with general data governance, API authorization, rate limiting, and privacy redaction policies (e.g., suppress physician home address from consumer-facing report output).
- **Data Retention:** FCRA § 1681c time ceilings (7-year / 10-year) are removed. Replaced with: user purchase/search history retained 2 years then deleted; physician profile data retained indefinitely as long as accurate (public record — no ethical reason to suppress); CCPA deletion requests honored for CA residents within 45 days.
**Locked:** Yes.

---

## Entry 008 — Domain: researchyourdoctor.com

**Date:** 2026-05-24
**Decision:** The public domain for this platform is **researchyourdoctor.com**.
**Reason:** Clear, patient-first framing. Zero ambiguity about the product's purpose. Chosen by Jay.
**Impact:** Partial resolution of Entry 003 — domain is now locked. AWS account and region still needed to complete Entry 003.
**Locked:** Yes.

---

## Entry 009 — Observability Deployment Topology (Phase 1-D)

**Date:** 2026-05-24
**Decision:** The locked observability stack (OpenTelemetry → Prometheus, Loki, Tempo, Grafana, Sentry) is deployed as:
- OTel Collector in **agent (DaemonSet) + gateway (Deployment)** mode. All 12 services push OTLP to the gateway, which fans out to the three backends.
- **kube-prometheus-stack** for Prometheus + Alertmanager (bundled Grafana disabled).
- **Grafana** from its own chart, with datasources and dashboards provisioned from `src/observability/grafana/`.
- **Loki and Tempo** back their storage on **S3** (IRSA, no static credentials), retention 30d logs / 14d traces.
- All secrets (Grafana admin, Sentry DSNs) pulled from **AWS Secrets Manager via External Secrets Operator**.
- PII scrubbing enforced at two layers: OTel collector processor + Sentry `before_send`.

**Reason:** Matches the locked stack and the existing infra (EKS `observability` namespace + IRSA already provisioned in the iam module). Config-as-code, non-deployed, consistent with the Phase 1-B IaC pattern.

**Sentry hosting (Resolved 2026-05-25):** **Sentry SaaS.** PII is already scrubbed at two layers (OTel collector `attributes/scrub_pii` + Sentry `before_send`, `send_default_pii=False`, SSN/email redaction) before any payload leaves the SDK, which mitigates the off-cluster residency concern for a pre-revenue non-CRA product. Self-hosted Sentry (Relay/Kafka/ClickHouse/Postgres) is not justified by the residual risk at this stage. The Sentry region is pinned at wiring time. **Revisit trigger:** if the product ever ingests actual PHI (beyond public-record physician data + consumer account/payment data), re-evaluate self-hosted or a BAA-backed plan before continuing.

**Impact:** Phase 1-D config is complete and validated. Deployment waits on Entry 003 (AWS account/region) and the Phase 1-E GitOps layer.
**Locked:** Topology yes; Sentry hosting mode yes — SaaS (2026-05-25).

---

## Entry 010 — GitOps + CD Topology (Phase 1-E)

**Date:** 2026-05-24
**Decision:** The continuous-delivery layer is ArgoCD in an **app-of-apps** pattern, defined entirely in `src/gitops/`.
- A single root Application (`bootstrap/root-app.yaml`) watches `argocd/apps/` and renders one child Application per platform component.
- **Deploy order is encoded as `argocd.argoproj.io/sync-wave` annotations** (waves 0-5): External Secrets Operator + observability namespace (0) → External Secrets CRs (1) → kube-prometheus-stack, which installs the monitoring CRDs (2) → Loki, Tempo, ServiceMonitors, PrometheusRules, OTel pipeline ConfigMap (3) → OTel gateway + agent, Grafana provisioning ConfigMaps (4) → Grafana (5).
- **Helm charts are pinned** in `charts-lock.yaml` (single source of truth); each chart-backed Application is a multi-source app pulling the pinned chart from upstream and its value file from this repo via the `$values` ref. The Phase 1-E test suite fails CI if any Application drifts from the lock or uses a floating revision.
- **Raw 1-D manifests** (namespace, External Secrets CRs, ServiceMonitor) are applied as directory sources with `directory.include` globs. The 1-D Prometheus rule files are raw rule groups, not CRDs, so Phase 1-E wraps them in `PrometheusRule` CRDs under `argocd/monitoring/`; a parity test guarantees they never diverge from the source.
- **Grafana datasources/dashboards** and the **OTel gateway pipeline** are turned into ConfigMaps by kustomize `configMapGenerator` overlays co-located with the 1-D files, so kustomize stays within its own root and ArgoCD's default `RootOnly` load restrictor is preserved (no security relaxation, no duplication).
- **Deploy-time PLACEHOLDER guard** (`scripts/gitops-guard.sh`, `make gitops-guard`) blocks any sync while account-specific PLACEHOLDER values survive. It is a deploy gate, not a CI gate — CI (`gitops-validate.yml`) validates structure and runs `kustomize build`, but does not run the guard, since PLACEHOLDERs are expected until Entry 003.

**Reason:** Matches the locked stack (GitOps: ArgoCD; CI/CD: GitHub Actions) and the existing non-deployed pattern. Pinned versions + parity tests + the placeholder guard make the layer safe to author now and safe to deploy the moment Entry 003 resolves.

**Open wiring (finalized at deploy):** The OTel **gateway** must mount the `otel-gateway-pipeline` ConfigMap and run with `--config` pointing at it. The exact opentelemetry-collector chart keys (`configMap.create` / `extraVolumes` / `command`) are pinned against the live chart version before first deploy; left out of the manifest now to avoid committing an unverified chart binding.

**Impact:** Phase 1-E complete and validated (config + `kustomize build` + 138 unit tests). Deployment waits on Entry 003 (AWS account/region) and the bootstrap step (install ArgoCD onto the 1-B cluster).
**Locked:** Topology yes; OTel gateway config-mount wiring and per-env value overlays open until Phase 1-F.

---

## Entry 011 — Workload Namespace Topology (Phase 1-G)

**Date:** 2026-05-25
**Decision:** Application services run in **per-group Kubernetes namespaces**, not a single shared namespace. The groups come from the Phase 1-B `iam` module, which already provisions IRSA roles for `app_namespaces = ["api-gateway", "identity", "reports", "workers", "observability"]` and trusts the service account `${namespace}/${namespace}-sa`. So: the api-gateway runs in namespace **`api-gateway`** with service account **`api-gateway-sa`**; identity-resolution services in `identity`; report/search in `reports`; async workers in `workers`.
**Reconciliation:** The Phase 1-D ServiceMonitor (`src/observability/prometheus/servicemonitors.yaml`) had `namespaceSelector.matchNames: ["medpro"]`, which assumed a single namespace and predated this lock. It is updated to select the four workload namespaces so Prometheus actually scrapes the services. (The `matchExpressions` over the 12 services is unchanged; 1-D tests still pass.)
**Reason:** The IRSA trust policy is the authoritative, already-locked constraint (it's infra, Phase 1-B). Per-namespace isolation also gives cleaner NetworkPolicy and RBAC boundaries than one flat namespace. The `medpro` single-namespace assumption was the stale element.
**Risk acknowledged:** Cross-namespace service discovery (e.g. gateway → report service) uses fully-qualified DNS (`svc.<ns>.svc.cluster.local`); NetworkPolicies must allow the required cross-namespace paths. Tracked for Phase 1-H (OPA/NetworkPolicy baseline).
**Locked:** Yes.

---

## Entry 012 — OPA Baseline Topology (Phase 1-H)

**Date:** 2026-05-25
**Decision:** Component C2 (OPA) is deployed as a **per-service sidecar**, starting with the api-gateway. The policy bundle is authored once in `src/policy/` (packages `medpro.authz` + `medpro.redaction`) and delivered as the `opa-policy` ConfigMap into a service's namespace by a dedicated ArgoCD app.
- **Decision API binds to `127.0.0.1:8181`** (same-pod only) — never exposed on the Service or pod network. Health + metrics bind to the diagnostic port `8282` for kubelet probes and Prometheus scrape.
- **The gateway's authz hook is switched on in-cluster** via `OPA_ENABLED=true` + `OPA_URL=http://127.0.0.1:8181` on the Deployment. The Python code default stays `opa_enabled=false` so local `make run-gateway` runs without a sidecar. The hook was already wired fail-closed in Phase 1-G (deny or unreachable both block).
- **Authz baseline:** default-deny; a `consumer` may create a report + read consumer surfaces; scoped `"<action>:<resource>"` permissions override role rules; `admin` is scoped to the `admin*` surface.
- **Redaction baseline (Entry 007):** `medpro.redaction` suppresses physician personal PII (home address, personal phone/email, DOB, SSN) from consumer-facing output; public-record professional data is always retained. Consumed by the Report Generation Service (C17, Phase 2); shipped now so the contract exists and is tested.
- **OPA image** is the pinned upstream public image (`openpolicyagent/opa:0.70.0-rootless`), not an account-specific PLACEHOLDER. It is not a Helm chart, so it is not tracked in `charts-lock.yaml`; mirror it through ECR pull-through at deploy if a private registry is required.
- **NetworkPolicy baseline** for the `api-gateway` namespace (the cross-namespace paths Entry 011 introduced): default-deny ingress+egress; allow DNS; allow API ingress from the ingress tier + metrics scrape from `observability`; allow egress to `identity`/`reports`/`workers`, to the OTel gateway, and external HTTPS:443 (Auth0 JWKS now, Stripe in Phase 2-J).
**Reason:** Sidecar-per-service is OPA's recommended deployment model (lowest latency, no shared-availability dependency) and fits the per-namespace topology locked in Entry 011. A single authored bundle keeps policy DRY across future sidecars.
**Risk acknowledged:** Each additional service needs the `opa-policy` ConfigMap replicated into its namespace (one small ArgoCD app per service). NetworkPolicy specifics (the exact ALB ingress source, downstream service ports) are finalized at deploy when those Services and the ingress controller exist. Policy enforcement is unverified against a live OPA + cluster (no cluster — Entry 003); validated by `opa test` (16 unit tests) and `kustomize build` only.
**Locked:** Sidecar topology + baseline policies yes; ALB ingress source + downstream egress ports open until those components land.

---

## Entry 013 — Audit Ledger Service Topology (Phase 1-I)

**Date:** 2026-05-25
**Decision:** The audit ledger service (component C5-audit) runs in the **`workers`** namespace with service account **`workers-sa`**.
- The locked workload topology (Entry 011) has four namespaces — `api-gateway`, `identity`, `reports`, `workers` — and no dedicated `audit` namespace. The audit ledger is an internal, non-public backend writer, which fits `workers` (gateway/identity/reports are each a different concern). Reusing the existing locked IRSA avoids a unilateral change to locked 1-B infra.
- The service is **internal only**: a ClusterIP Service, no Ingress, reached intra-cluster from the event-emitting services and gated by the `workers` NetworkPolicy baseline (default-deny + DNS + ingress from api-gateway/identity/reports/workers + metrics scrape from observability + egress to Postgres 5432, the OTel gateway, and HTTPS:443 for AWS APIs/IRSA).
- **Scope:** Phase 1-I is **Aurora-only**. The ledger writes to the `medpro_audit` DB as the INSERT-only `medpro_audit_writer` role (migration 0003); UPDATE/DELETE are blocked by the `deny_audit_mutation` trigger + RLS. The **S3 WORM export** of the chain is Phase **4-F** ("Audit Ledger Phase 2"), so the `audit_writer` S3 IAM policy (defined but unattached in the 1-B iam module) stays unattached until then.
- **Chain model:** hash chains are **per target** — keyed by `(target_type, target_id)` — matching the `audit_events` column semantics; checkpoints are **per target_type**, matching `audit_chain_checkpoints`. The service computes `prev_event_hash`/`event_hash` (the canonical `AuditEvent` model carries the fields + `compute_hash` but does not own the chain).
**Reason:** Honors the locked Entry 011 topology without changing infra; keeps the audit writer's blast radius minimal (internal, INSERT-only DB role, no public route); defers the S3 layer to its planned phase.
**Risk acknowledged:** Sharing the `workers` namespace with future async workers means the namespace-wide default-deny is opened per-service (audit-service opens only its own paths; later workers add theirs). If isolation requirements grow, a dedicated `audit` namespace can be added later via an iam `app_namespaces` change (a new decision). NetworkPolicy egress specifics (the exact Aurora DB-subnet CIDR for 5432, VPC endpoints for 443) finalize at deploy. The ledger is an in-memory shell until `AUDIT_DATABASE_URL` is wired — unverified against a live DB + RLS.
**Locked:** Namespace + internal-only + Aurora-only scope yes; DB-subnet/VPC-endpoint CIDRs open until deploy; dedicated audit namespace deferred.

---

## Entry 014 — Source Connector Framework Design (Phase 2-A)

**Date:** 2026-05-25
**Decision:** The Source Connector Framework (component C9) lives in `src/connectors/` as a **library** (not a deployed service — adapters run as workers/Temporal activities later). Design choices:
- **Async-first** (`httpx`), per the locked stack (tool-recommendations). Tests drive the async code with `asyncio.run` from sync test functions, so **no `pytest-asyncio` dependency** is added (it is declared in pyproject but not installed in CI/local; the existing suite has no async tests).
- **Retry/backoff is in-house** (`retry.py`) — exponential backoff with full jitter, honoring `Retry-After`. The locked stack names `httpx` for HTTP and nothing for retry; rather than introduce `tenacity`, the framework stays dependency-free and fully injectable (sleep/clock/rng).
- **A connector's output is a `RawRecord`** (raw payload + content-addressed SHA-256 via `DataProvenance.hash_raw`), **pre-normalization**. Turning a RawRecord into a typed `NormalizedRecord` is C11 (Phase 2-D), deliberately kept out of C9.
- **Error taxonomy** maps each failure to `retryable` + a `SourceStatus`; the framework classifies HTTP responses (429 → rate-limited, 401/403 → auth, 5xx/timeouts → retryable unavailable, other 4xx → permanent).
- **Schema-drift = contract** (`SchemaContract`): adapters declare required fields/types; the framework validates each raw record at runtime and raises `SchemaDriftError` (SCHEMA_DRIFT health) rather than emitting malformed records silently — directly addressing architecture risk **R6**.
- **`run()` produces a `SourceHealthRecord`** (the existing C24 schema) every run, so the Source Health Monitor has a uniform signal.
**Reason:** Matches the locked stack and the "what to avoid" list (no ad-hoc scraping outside the C9 framework, no homegrown auth, no unnecessary deps). Pre-normalization output keeps C9/C11 cleanly separated. The contract guard operationalizes R6.
**Legal gate:** C9 is the **framework only** — it fetches no live source. Real ingestion is in the C10 adapters (Phase 2-B+), each governed by the Phase 0 legal gate and its per-source ToS/clearance tier (Source Priority Matrix).
**Risk acknowledged:** The default `httpx.AsyncClient` transport path is present but untested (tests always inject a stub transport); it is exercised when the first real adapter lands. The per-instance `RateLimiter` is a per-replica floor — a Redis-backed global limiter (ElastiCache) is layered on when adapters run multi-replica.
**Locked:** Framework design + package location + async-first + RawRecord output yes; the global rate-limiter and real transport land with the first adapter.

---

## Entry 015 — NPPES Adapter Mode + Federal Adapter Layout (Phase 2-B.1)

**Date:** 2026-05-25
**Decision:** The first C10 adapter — NPPES / NPI Registry (source F1) — and the layout the rest of the federal batch follows:
- **Adapters live in `src/connectors/sources/`** (one module per source), separate from the C9 framework package root. The `sources` package `__init__` carries the legal-gate notice and the F1/F2/F3 build inventory.
- **NPPES builds the API-lookup mode first** (`REST_API`): a per-provider query against the public CMS NPPES API (`/api/?version=2.1`), paginated via `skip` (page cap 200, skip cap 1000). This is the mode the report pipeline uses on-demand. The **monthly bulk-download** mode (the full dissemination file) is a deferred follow-on adapter — the Source Priority Matrix lists F1 as "Bulk-DL monthly + API lookup", but the on-demand lookup is the MVP-critical path and the natural first build on the framework's `request()` HTTP helper.
- **Query is a validated value object** (`NppesQuery`): requires at least one of `number` / `last_name` / `organization_name` (NPPES rejects a version-only query); `to_params()` emits only the set fields.
- **SchemaContract guards `{number, enumeration_type, basic, addresses, taxonomies}`** with type checks on the latter four — the R6 drift guard for F1.
- **NPPES's HTTP-200-with-`Errors` failure mode** (it reports bad queries as a 200 carrying an `Errors` array, not a 4xx) is mapped to a non-retryable `PermanentError` so a rejected query surfaces as a failed run rather than a silent zero-record success.
**Reason:** Keeps the framework package framework-only (Entry 014) while giving the federal batch a predictable home. API-lookup-first matches how reports consume F1 (per-NPI) and is fully contract-testable against the C9 harness with a stubbed transport.
**Legal gate:** Built and tested against **stubbed transports only — no network I/O**. Live ingestion against the NPPES endpoint is a deploy-time action governed by the Phase 0 FCRA determination (F1 is T1/L0 open-data, the lowest-risk tier).
**Locked:** Adapter layout (`src/connectors/sources/`), NPPES API-lookup-first, `NppesQuery` contract. Bulk-download mode + the Redis-backed global rate limiter remain deferred.

---

## Entry 016 — OIG LEIE Adapter Mode (Phase 2-B.2)

**Date:** 2026-05-25
**Decision:** The OIG LEIE (List of Excluded Individuals/Entities) adapter — source F2 — ships as a **bulk-download-first** adapter (`IntegrationMethod.BULK_DOWNLOAD`):
- **Primary mode: monthly bulk CSV** from `https://oig.hhs.gov/exclusions/downloadables/LEIE.csv`. Each row is one excluded individual or entity; `csv.DictReader` parses it into a dict per row, yielded directly by `fetch_raw`. All field values are strings (standard CSV semantics). The adapter downloads the entire file in one `self.request()` call, then iterates synchronously — the LEIE file is ~5 MB (70 000+ rows), which fits in memory without streaming.
- **`_parse_csv_text()` helper** extracts the `resp.text` string and raises `SourceUnavailableError` (retryable) if the response is empty or the `.text` property raises — surfacing download failures as `SourceStatus.DOWN` rather than silent empty runs.
- **`SchemaContract` guards 11 columns**: `LASTNAME`, `FIRSTNAME`, `BUSNAME`, `NPI`, `EXCDATE`, `EXCLTYPE`, `ACTION`, `ADDRESS`, `CITY`, `STATE`, `ZIP` — the identity + exclusion-fact + location set. Columns that are informational or frequently blank (`MIDNAME`, `UPIN`, `SPECIALTY`, `REINDATE`, `WAIVERDATE`, `WAIVERSTATE`) are not guarded to avoid alerting on OIG adding optional columns; their absence would not break downstream normalization.
- **NPI may be an empty string** — providers excluded before May 2008 (pre-NPI-era) may not have an NPI. Empty string is valid per the contract (`str` type passes, empty string is a valid string); downstream callers treat it as "NPI not recorded."
- **API spot-check (per-NPI real-time lookup)** is deferred. For the MVP, LEIE checking is an in-memory or in-DB lookup against the bulk-loaded data, not a live API hit per report request. The OIG exclusion search is HTML-based (no documented JSON endpoint); an unofficial spot-check adapter is a follow-on.
- **`expected_min_records` default is `None`** (no threshold enforced). Production deployments should override to ~60 000 to catch truncated downloads.
**Reason:** The bulk CSV is the canonical, complete LEIE dataset — it is the authoritative source OIG maintains and it is the most efficient path for the MVP (one download loads all exclusions; per-NPI checks run in-memory). This mirrors the "bulk-first" design rationale of Entry 015 (NPPES). The CSV parse approach matches the actual OIG data format and avoids the risk of building on an undocumented API.
**Legal gate:** Built and tested against **stubbed transports only — no network I/O**. Live ingestion against the OIG endpoint is a deploy-time action governed by the Phase 0 FCRA determination (F2 is T1/L0 open-data — U.S. Government Work, public domain per 17 U.S.C. § 105).
**Locked:** BULK_DOWNLOAD mode, CSV-based parse, 11-field contract, empty-NPI allowance. API spot-check adapter deferred.

---

## Entry 017 -- SAM.gov Exclusions Adapter Mode (Phase 2-B.3)

**Date:** 2026-05-25
**Decision:** The SAM.gov Exclusions adapter -- source F3 -- ships as a **paginated REST API** adapter (`IntegrationMethod.REST_API`):
- **Primary mode: paginated JSON API** against `https://api.sam.gov/entity-information/v3/exclusions`. The endpoint is free with a self-service API key from SAM.gov (CC0/public domain). Each page request carries `api_key`, `page` (0-indexed), and `size` (max 100). `totalRecords` from the first response page drives pagination depth. Pagination terminates when either: (a) a page returns an empty `entityData` list (explicit sentinel), or (b) `(page + 1) * page_size >= totalRecords` (all known records fetched). If `totalRecords` is absent, pagination relies solely on the empty-page sentinel -- a safe fallback that avoids an infinite loop on a malformed response.
- **API key is a constructor arg**, not baked into `ConnectorConfig`. In deployed environments it comes from External Secrets Operator / Secrets Manager wired to the workers-sa IRSA role. This follows the connector framework convention ("secrets are passed at construction time, not config time") established in Phase 2-A.
- **`SchemaContract` guards two top-level keys** in each `entityData` item: `exclusionDetails` (dict) and `entityRegistration` (dict). These two nested dicts are the stable structural contract -- `exclusionDetails` carries the exclusion fact (type, date, agency, NPI link); `entityRegistration` carries identity (UEI, legal name). Individual sub-keys within each dict are not guarded here; their mapping into typed signals is C11 normalization (Phase 2-D). The two-dict contract is the right granularity: it fires the R6 alarm if SAM.gov restructures its response (e.g., flattens the nested shape) without alerting on new optional sub-keys SAM.gov may add to either dict.
- **`expected_min_records` default is `None`** (no threshold enforced). Production deployments should override to ~70 000 to catch truncated runs (the SAM.gov exclusions dataset contains ~80 000 active exclusions as of 2026).
- **Delta-sync mode** (daily incremental using an `updatedDate` filter to fetch only new/changed exclusions) is a deferred follow-on. For the initial build and MVP, a full re-page is sufficient; the delta path lands once data volume makes full re-pages operationally expensive.
- **REST_API** (not BULK_DOWNLOAD): the paginated JSON API is the natural integration method -- SAM.gov does publish bulk extract files (`/data-services/v1/extracts?fileType=EXCLUSION`), but these require a higher-tier API key and produce a zipped archive that is harder to integrate than the standard paginated JSON endpoint. The JSON API is the documented, stable path for programmatic exclusion lookups.
**Reason:** Matches the source priority matrix ("API-key bulk + daily delta sync") and the locked connector framework design (REST_API path in C9, consistent with F1's NPPES adapter). The paginated JSON endpoint is the lowest-friction authoritative source for SAM.gov exclusions -- free API key, CC0 data, standard JSON pagination.
**Legal gate:** Built and tested against **stubbed transports only -- no network I/O**. Live ingestion against the SAM.gov endpoint is a deploy-time action governed by the Phase 0 FCRA determination (F3 is T1/L0 open-data -- U.S. Government Work, public domain per 17 U.S.C. § 105).
**Locked:** REST_API mode, paginated JSON endpoint, two-dict contract, api_key-as-constructor-arg. Delta-sync and bulk-extract modes deferred.

---

## Entry 018 -- CMS Care Compare Adapter Mode (Phase 2-B.4)

**Date:** 2026-05-25
**Decision:** The CMS Care Compare adapter -- source F4 -- ships as a **paginated Socrata SODA REST API** adapter (`IntegrationMethod.REST_API`):
- **Primary mode: paginated Socrata SODA 2.0 API** against `https://data.cms.gov/resource/{dataset_id}.json`. The endpoint requires no API key (CC0/public domain). Pagination uses `$limit` + `$offset` + `$order=:id` (Socrata system row ID -- the only stable key for deterministic pagination across CMS's ~3 million row dataset). Termination fires when the response array is shorter than `$limit` (the Socrata short-page sentinel: the source returns exactly as many records as remain). An empty array also terminates. This is simpler and more robust than totalRecords math (Socrata SODA 2.0 does not return a totalRecords envelope field).
- **Dataset ID is a configurable constructor arg** (default: `mj5m-pzi6`, the Doctors and Clinicians national downloadable file). CMS has superseded this dataset before; making the ID configurable means the adapter survives a dataset refresh without a code change.
- **One row per practice location per NPI.** The Doctors and Clinicians dataset has one row per NPI per practice address. A provider with five locations yields five rows with the same NPI. The adapter yields all rows as-is; grouping and deduplication by NPI is C11 normalization (Phase 2-D), not the adapter's responsibility.
- **`SchemaContract` guards 8 fields**: `npi`, `ind_pac_id`, `last_name`, `first_name`, `pri_spec`, `assgn`, `cty`, `st` with `str` type checks. These cover: identity-link to NPPES (`npi`), CMS-specific identity (`ind_pac_id`), provider name (`last_name`, `first_name`), clinical signal (`pri_spec` -- primary specialty), participation flag (`assgn` -- accepts Medicare assignment), and practice location (`cty`, `st`). The contract fires the R6 alarm if CMS restructures its schema or renames these core fields; extra columns (which CMS adds occasionally) pass through without alerting.
- **No API key.** The Socrata public endpoint is unauthenticated. An optional `X-App-Token` header raises the rate limit ceiling but is not required for a single scheduled monthly ingest.
- **`expected_min_records` default is `None`** (no threshold enforced). Production deployments should override to ~2 000 000 to catch truncated runs.
**Reason:** The Socrata SODA API is the standard, stable integration path for `data.cms.gov` datasets. All CMS public provider datasets use this format; building to SODA means the pattern is reusable for F4, I1, I2, and any other CMS data.cms.gov datasets the platform adds. The short-page termination is idiomatic for SODA (no separate total-count request needed). The `$order=:id` is the correct Socrata pagination anchor for large datasets.
**Legal gate:** Built and tested against **stubbed transports only -- no network I/O**. Live ingestion against data.cms.gov is a deploy-time action governed by the Phase 0 FCRA determination (F4 is T1/L0 open-data -- CC0 license, explicitly noted on data.cms.gov/provider-data).
**Locked:** SODA REST_API mode, `$limit`/`$offset`/`$order=:id` pagination, short-page termination, configurable `dataset_id`, 8-field contract.

---

## Entry 019 -- CMS Medicare Enrollment Adapter Design (Phase 2-B.5)

**Date:** 2026-05-25
**Decision:** The CMS Medicare Enrollment adapter -- source I1 -- ships as a **single connector that fetches two data.cms.gov SODA datasets in sequence** (`IntegrationMethod.REST_API`):

- **Two datasets, one connector.** I1 covers two complementary Medicare signals: (1) Medicare FFS Provider Enrollment records (active participation, provider type, CMS enrollment ID) and (2) Medicare Opt-Out Affidavits (providers who have elected private-pay-only -- a high-value red flag). Both are CC0/T1/L0 open-data on `data.cms.gov`. The source-priority matrix (Entry 014 build sequence) lists them as a single I1 source. A single connector keeps the C24 Source Health Monitor's source inventory clean and avoids a proliferation of single-signal connectors for what is semantically one Medicare relationship signal pair.
- **Two schema contracts.** `enrollment_contract` guards 6 fields (`npi`, `last_name`, `first_name`, `enroll_id`, `provider_type_desc`, `state_cd`). `opt_out_contract` guards 5 fields (`npi`, `last_name`, `first_name`, `optout_effective_date`, `order_refer_flag`). Each is applied per-record inside `fetch_raw` before yielding; the base-class single-contract path is suppressed (`contract = None`). `optout_end_date` is intentionally excluded from the opt-out contract: it is null for active opt-outs (the common case), and requiring it would cause false-positive SCHEMA_DRIFT alerts on nearly every row.
- **`_record_type` tag.** Each yielded row is tagged with `_record_type = "enrollment"` or `_record_type = "opt_out"` before the contract is applied. C11 normalization (Phase 2-D) uses this tag to route each record to the correct signal extractor on the `CanonicalProviderProfile` without re-inspecting the payload shape.
- **Same SODA pagination pattern as F4.** `$limit` + `$offset` + `$order=:id`, short-page sentinel termination. No API key required.
- **Configurable dataset IDs.** `enrollment_dataset_id` (default: `s2uc-8wxp`) and `opt_out_dataset_id` (default: `7tef-9pja`) are constructor args. Both must be verified against `data.cms.gov/provider-characteristics` before first live ingest.
- **Graceful partial result.** If the enrollment pass succeeds but the opt-out pass fails (e.g., source unavailable), `run()` returns `FetchStatus.PARTIAL` -- enrollment records are preserved. Schema drift in either pass stops the run with `FetchStatus.FAILED` and `SourceStatus.SCHEMA_DRIFT`.
- **`expected_min_records` default is `None`** (covers both datasets combined). Production deployments should override to ~900 000 to catch truncated runs.

**Reason:** The two datasets are semantically coupled (both describe a provider's Medicare relationship), are both on `data.cms.gov` SODA, and are always ingested together in the monthly batch. A single connector is the correct abstraction. The `_record_type` tag preserves routing information for C11 without re-parsing or adding a second pass over the record list.
**Legal gate:** Built and tested against **stubbed transports only -- no network I/O**. Live ingestion is governed by the Phase 0 FCRA determination (I1 is T1/L0 open-data -- CC0).
**Locked:** Single connector for I1 enrollment + opt-out, two per-type contracts in `fetch_raw`, `_record_type` tag, configurable dataset IDs.

---

<!-- Add new entries below this line -->
