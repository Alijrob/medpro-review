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

## Entry 021 -- NPPES Specialty Crosswalk Design (Phase 2-B.7 / I4)

**Date:** 2026-05-25
**Decision:** I4 (NPPES Specialty Crosswalk) ships as a **helper module, not a SourceConnector**. It is a derived signal: the NUCC taxonomy codes already captured in F1 (NPPES) RawRecords are mapped to human-readable specialty group names. No additional network fetch is needed. Location: `src/connectors/sources/nppes_taxonomy.py`.

- **`TAXONOMY_CROSSWALK: dict[str, str]`** -- maps NUCC taxonomy codes (uppercase, 10-char) to specialty group name strings. Covers ~200+ most commonly encountered codes in clinical practice, organized by NUCC grouping. Unmapped codes return `None` (graceful degradation). The table should be verified against the official NUCC release (https://www.nucc.org/index.php/code-sets-mainmenu-41) before the first live ingest and kept current.
- **`crosswalk_taxonomy_code(code: str) -> str | None`** -- direct lookup; normalizes input to uppercase before lookup.
- **`infer_specialty_group(taxonomies: list[dict]) -> str | None`** -- takes an NPPES `taxonomies` array; prefers the taxonomy with `primary == True`, falls back through non-primary entries in order. Returns `None` if nothing maps. Used in C11 normalization (Phase 2-D) to populate `specialty_group` on a `CanonicalProviderProfile`.
- **No SourceConnector subclass.** No health record, no fetch result, no contract. The crosswalk is pure data + pure functions; it is exercised by 31 unit tests (no stubbed transport needed).

**Reason:** Source-priority.md explicitly notes: "Derived signal -- taxonomy codes from NPPES crosswalk to specialty groups. Build as part of the NPPES adapter (no separate adapter needed)." Adding a connector would be misleading -- no source fetch occurs. A standalone helper module with clean exports from `connectors.sources` is the correct abstraction.
**Locked:** Helper module pattern; `crosswalk_taxonomy_code` + `infer_specialty_group` as the C11 normalization interface.

---

## Entry 022 -- PubMed / NCBI Entrez Adapter Design (Phase 2-B.8 / A1)

**Date:** 2026-05-25
**Decision:** The PubMed adapter -- source A1 -- ships as a **per-provider on-demand lookup adapter** that uses a **two-step NCBI Entrez API call sequence** per batch (`esearch` -> `esummary`):

- **Two requests per batch.** NCBI Entrez requires a separate esearch call (returns PMIDs) and an esummary call (returns article metadata). Both are made inside `fetch_raw` per page of PMIDs. Both pass through the C9 `request()` helper for throttling, retry, and HTTP->error classification. This is the only adapter in the P1 batch that requires two requests per iteration.
- **Author-name search (`{name}[Author]`).** NCBI PubMed does not index by NPI; the search term is a provider's name. Name disambiguation (separating the target provider's publications from namesakes) is a C11 normalization concern, not the adapter's. The adapter yields all matching articles.
- **Pagination via `retstart` + `retmax`.** Standard NCBI Entrez pagination; stops on a short esearch page (fewer PMIDs than `retmax`). `retmax` defaults to 200 (well under NCBI's 10 000 per-request limit).
- **`api_key` as optional constructor arg.** Unauthenticated rate limit: 3 req/s. With a key: 10 req/s. The key is passed as an `api_key` query parameter on all Entrez requests; it is never in `ConnectorConfig`.
- **4-field contract.** Guards `uid` (PMID, str), `title` (str), `pubdate` (str), `authors` (list) -- the fields present on every NCBI esummary PubMed article. Extra fields (journal, doi, pages, etc.) pass through.
- **`expected_min_records=None`.** Per-provider publication counts vary widely (0 for most generalists; hundreds for academic researchers). No floor is enforced by default.

**Reason:** A1 is fundamentally different from F2-I2: it is not a batch/bulk source but an on-demand per-provider lookup by author name. The two-step esearch+esummary pattern is NCBI's documented approach. The adapter correctly models this without additional framework machinery.
**Legal gate:** Built and tested against **stubbed transports only**. A1 is public domain (NIH/NLM), T1/L0.
**Locked:** Two-step esearch+esummary, `retstart`/`retmax` pagination, `author_name` + `api_key` as constructor args, 4-field contract.

---

## Entry 023 -- ClinicalTrials.gov Adapter Design (Phase 2-B.9 / A2)

**Date:** 2026-05-25
**Decision:** The ClinicalTrials.gov adapter -- source A2 -- ships as a **per-provider on-demand lookup adapter** using the **ClinicalTrials.gov API v2** with **cursor-based pagination** (`pageToken`):

- **API v2 cursor pagination.** Unlike SODA-style offset pagination (F4, I1, I2) or NCBI `retstart` pagination (A1), ClinicalTrials.gov v2 uses an opaque `pageToken` cursor. Each response either includes `nextPageToken` (more pages) or does not (last page). The adapter stops when `nextPageToken` is absent from the response.
- **Investigator-name search (`{name}[Investigator]`).** ClinicalTrials.gov does not support NPI-based investigator lookup; the search term is a provider's name. Disambiguation is C11 normalization.
- **Single structural contract.** Guards `protocolSection` (dict) on each study record. Inner sub-modules (`identificationModule`, `statusModule`, `contactsLocationsModule.overallOfficials`) are not contract-guarded to avoid false-positive drift if ClinicalTrials.gov reorganizes its nested schema. C11 normalization extracts NCT ID, status, phase, and investigator role.
- **No API key.** ClinicalTrials.gov v2 is public, no key required or available.
- **`page_size` defaults to 200.** API supports up to 1000 per page; 200 is conservative.
- **`expected_min_records=None`.** Most providers have zero trials; no floor enforced by default.
- **Simpler than A1.** Single request per page (no two-step sequence); cursor handles continuation.

**Reason:** A2 is the natural companion to A1: same "build with A1 batch" note in source-priority.md, same per-provider on-demand pattern. ClinicalTrials.gov v2 cursor pagination is a cleaner API than NCBI retstart (no totalCount needed; last page is self-signaling via absent `nextPageToken`). Single contract guard is the right tradeoff given the deeply nested response structure.
**Legal gate:** Built and tested against **stubbed transports only**. A2 is public domain (NIH), T1/L0.
**Locked:** ClinicalTrials.gov API v2, cursor pagination, `investigator_name` as constructor arg, single `protocolSection` contract.

## Entry 020 -- CMS Medicaid Enrollment Adapter Design (Phase 2-B.6)

**Date:** 2026-05-25
**Decision:** The CMS Medicaid Enrollment adapter -- source I2 -- ships as a **single-dataset Socrata SODA REST API** adapter (`IntegrationMethod.REST_API`), simpler than I1's two-dataset design:

- **Single dataset, single pass.** Unlike I1 (Medicare Enrollment + Opt-Out Affidavits = two SODA datasets), I2 covers a single signal: Medicaid provider enrollment participation by state. One dataset, one `fetch_raw` pass, standard base-class contract path (no `_record_type` tagging, no `contract = None` suppression needed). This is the appropriate design because there is no Medicaid opt-out equivalent and no second dataset that semantically belongs to the same I2 source entry.
- **SODA pagination pattern.** `$limit` + `$offset` + `$order=:id`, short-page sentinel termination -- identical to F4 (Care Compare) and I1 (Medicare Enrollment). No API key required.
- **5-field schema contract.** Guards: `npi` (identity anchor), `last_name` + `first_name` (identity confirmation), `state_cd` (critical -- Medicaid is state-administered; state is the primary grouping dimension), `provider_type_desc` (specialty signal for primary care + pediatric coverage analysis). Extra columns pass through without SCHEMA_DRIFT. Contract field names should be verified against the live dataset schema before first live ingest.
- **Configurable `dataset_id`.** Default is a placeholder that must be verified against `data.cms.gov/provider-data` or `data.cms.gov/provider-characteristics/medicaid` before live ingest. CMS periodically refreshes datasets; making the ID configurable means the adapter survives a dataset refresh without a code change.
- **`expected_min_records` default is `None`** (no threshold enforced). Production deployments should override to a value consistent with the specific national CMS dataset size (likely tens of thousands to hundreds of thousands of records).
- **No `_record_type` tag.** I2 yields a single record type (Medicaid enrollment); the tag is unnecessary. C11 normalization (Phase 2-D) routes by `source_id == "I2"` rather than inspecting a record-type tag.

**Design contrast with I1:**
- I1: two datasets + two contracts + `_record_type` tag + `contract = None` + graceful PARTIAL result on second-dataset failure.
- I2: one dataset + one contract + standard base-class path. No partial-result complexity because there is no second pass to partially fail.

**Reason:** I2 is semantically a single signal (Medicaid participation). The additional complexity of I1's dual-dataset design is not warranted here. The SODA pattern is the established `data.cms.gov` integration path; reusing it keeps the P1 federal batch consistent and makes the C24 Source Health Monitor's adapter inventory simple to scan.
**Legal gate:** Built and tested against **stubbed transports only -- no network I/O**. Live ingestion is governed by the Phase 0 FCRA determination (I2 is T1/L0 open-data -- CC0, published on data.cms.gov).
**Pre-live checklist:** (1) Verify `DEFAULT_DATASET_ID` against `data.cms.gov/provider-data`; (2) verify `_MEDICAID_REQUIRED_FIELDS` field names against live dataset schema; (3) set `expected_min_records` in production config.
**Locked:** SODA REST_API mode, single dataset, single pass, 5-field contract, configurable `dataset_id`, standard base-class contract path.

---

## Entry 024 -- Source Health Monitor Design (Phase 2-C)

**Date:** 2026-05-25
**Decision:** Source Health Monitor (C24) ships as a FastAPI shell service (`src/backend/source_health_monitor/`) following the established Phase 1 service pattern (auth_service, api_gateway, audit_service). Key design choices:

- **FastAPI service shell.** Non-deployed; in-memory state; port 8002. Same pattern as every prior Phase 1/2 shell -- Aurora-backed in production (Entry 003), in-memory for local development and testing.
- **Two-table history model.** `source_health_records` (migration 0001) remains the current-state upsert table (one row per source). `source_health_history` (migration 0004) is the new append-only time-series table (one row per adapter run). C24 reads from `source_health_records` for fleet-summary queries and writes to `source_health_history` for trend/staleness analysis. The two-table design avoids unbounded row growth on the current-state table.
- **HealthStore owns accumulation; SourceHealthMonitor owns thresholds.** `base.py` always emits `consecutive_failures` of 0 (success) or 1 (failure) -- a single-run snapshot. `HealthStore.ingest()` accumulates the true running count across calls. `SourceHealthMonitor.evaluate()` is stateless: it receives the accumulated count and returns `HealthAlert` objects. This separation makes the threshold logic trivially unit-testable without any I/O.
- **Alert types: CONSECUTIVE_FAILURES, SCHEMA_DRIFT, STALE_SOURCE, LOW_RECORD_COUNT, AUTH_FAILURE.** Thresholds: failure_warning=3, failure_critical=5, stale_bulk=48h, stale_api=4h (all configurable via `MonitorSettings` / env). AUTH_FAILURE is always CRITICAL regardless of consecutive count.
- **Stale threshold split by integration method.** OIG LEIE (F2) is the only P1 BULK_DOWNLOAD source; its refresh cadence is monthly, so a 48h stale window is appropriate. All 7 REST_API sources use a 4h window. The `HealthStore` carries `_P1_SOURCES` registry so the integration method is always known from the source_id.
- **P1 inventory: 8 sources (not 9).** I4 (NPPES Specialty Crosswalk) is a derived helper module (DECISIONS.md Entry 021), not a `SourceConnector`. It emits no `SourceHealthRecord` and is excluded from the health monitor's P1 registry. The 8 monitored P1 connector sources are: F1, F2, F3, F4, I1, I2, A1, A2.
- **0003 seed divergence noted.** Migration 0003 seeded `source_health_records` with F1-F4 and F5-F9 (pre-Phase-2-B placeholders). Migration 0004 adds the correct Phase 2-B IDs (I1, I2, A1, A2) with ON CONFLICT DO NOTHING. The old F5-F9 rows are left in place to avoid altering a previously committed migration.
- **Alerting rules extended.** `src/observability/prometheus/rules/alerting-rules.yaml` gains `DataSourceConsecutiveFailuresWarning`, `DataSourceConsecutiveFailuresCritical`, and `DataSourceStale` (with bulk/API threshold split via `integration_method` label). The prior `DataSourceUnavailable` and `DataSourceSchemaDrift` rules (added in Phase 1-D) are retained unchanged.
- **`make run-monitor`** starts the shell on port 8002 (8000=auth, 8001=audit, 8002=monitor).

**Deferred / open:**
- DB-backed current-state upsert (Aurora `source_health_records`) and history append (`source_health_history`) when Entry 003 is resolved.
- Prometheus metric exports (`source_consecutive_failures`, `source_last_successful_run_age_seconds`) require an `/metrics` endpoint or OTel gauge; wired when the service is deployed and the ServiceMonitor scrapes it.
- ServiceMonitor for `source-health-monitor` already exists in the 1-D blanket ServiceMonitor (`servicemonitors.yaml`); no new ServiceMonitor needed.
- Active probe mode (C24 Phase 2 -- Phase 3-K): the MVP only ingests records from adapter push; Phase 3-K adds scheduled pull probes that run adapters on a cron.

**Locked:** FastAPI shell, two-table history model, HealthStore/SourceHealthMonitor separation, 8 P1 connector sources, alert types + thresholds as above, `make run-monitor` on port 8002.

---

## Entry 025 -- Normalization Layer Design (Phase 2-D, C11)

**Date:** 2026-05-25
**Decision:** Normalization Layer (C11) ships as a pure transformation library (`src/normalizers/`) following the same library pattern as the connector framework (src/connectors/). No deployed service, no network I/O, no state. Normalizers run as part of the ingest pipeline; later they become Temporal activities (C15).

Key design choices:

- **Library pattern.** `src/normalizers/` is a pure Python package: `SourceNormalizer` ABC + `NormalizationError` in `base.py`, registry in `registry.py`, concrete normalizers in `sources/`. Importing `normalizers.sources` triggers all `@register` decorations.
- **`normalize(raw, *, entity_npi=None)` signature.** Optional `entity_npi` keyword handles the NPI-routing split: F1/F4/I1/I2 extract NPI from raw and ignore the parameter; F2 (OIG LEIE) tries raw["NPI"] then falls back; F3/A1/A2 require the caller to supply the NPI (no NPI in raw). `_require_npi()` raises NormalizationError if the final NPI is missing or invalid.
- **`source_record_id` set here for all 8 P1 sources.** Deferred in every C10 adapter (DECISIONS.md Entries 015-023). C11 normalizers set it: NPI for F1/F4/I1/I2/F2, UEI for F3, PMID for A1, NCT ID for A2. This is the first point in the pipeline where `DataProvenance.source_record_id` is populated.
- **`_parse_date()` handles 6 formats.** ISO (YYYY-MM-DD), US slash (MM/DD/YYYY), US dash (MM-DD-YYYY), year+abbr-month ("2022 Jan"), year-month ("2022-01"), year-only ("2022"). Returns None for blank/unparseable inputs; normalizers raise NormalizationError for required date fields.
- **I4 taxonomy crosswalk applied in the F1 normalizer.** `get_specialty_group(nppes_record: NppesRecord) -> str | None` is exported from `normalizers.sources.f1_nppes`. C13 (Entity Linking & Merge) calls this when building the CanonicalProviderProfile. NppesRecord schema unchanged (no specialty_group field added -- profile is the right home for the derived string).
- **8 normalizers registered (I4 excluded).** F1, F2, F3, F4, I1, I2, A1, A2. I4 (NPPES Specialty Crosswalk) is a pure helper module with no SourceConnector and no normalizer -- its output is derived from F1 records, not from a raw fetch. Consistent with the C24 Source Health Monitor P1 inventory (Entry 024).
- **Address/TaxonomyCode parsing is defensive.** Invalid Pydantic fields (bad state code, short ZIP, non-conformant taxonomy code) are skipped rather than raising; a single bad address does not fail the whole record. Required fields (NPI, exclusion date, NCT ID) do raise NormalizationError.
- **`normalize()` top-level dispatch.** `normalizers.normalize(raw, entity_npi=...)` wraps `get_normalizer(raw.source_id).normalize(raw, ...)` for ergonomic single-call use by the pipeline.
- **`make normalizers-test`.** New Makefile target. `.github/workflows/normalizers-validate.yml` CI. `normalizers` package added to pyproject.toml.

**Deferred / open:**
- DB write path: normalized records are produced as Pydantic objects; persistence to `normalized_records` Aurora table (migration 0001) lands when the ingest pipeline (C15 Temporal) is wired in Phase 2-E/2-H.
- A1/A2 author disambiguation: `author_position` is None in the MVP; C13 resolves author identity via NPI + name/affiliation matching.
- F2 name-match path for pre-NPI-era exclusions (empty raw["NPI"], no entity_npi): normalizer raises NormalizationError; deferred to Phase 3 identity resolution.
- Address normalizer hardening: postal_code 9-digit long-form (13 chars including country prefix) is handled by _clean_zip; edge cases in NPPES international addresses are out of scope.

**Locked:** library pattern, 8-normalizer registry, normalize() signature with optional entity_npi, source_record_id set at C11, I4 crosswalk via get_specialty_group() helper, _parse_date() for 6 formats.

---

## Entry 026 — Identity Resolution MVP Design (C12, Phase 2-E)

**Date:** 2026-05-26  
**Status:** Locked  
**Author:** Claude (session 2026-05-26)

**Decision:** Build `src/identity/` as a pure in-memory library using NPI-exact-match as the sole matching strategy for the MVP. F1 (NPPES) is the identity anchor. A source-tier confidence model drives `identity_confidence` and `human_review_required` flags on `UnifiedIdBundle`.

**Key design choices:**

- **Library pattern.** `src/identity/` follows the same pattern as `src/normalizers/`: pure Python package, no network I/O, no deployed service, no state beyond the injected IdentityStore. Will run as Temporal activities in Phase 2-H.
- **NPI-exact-match only (MVP).** All C11-normalized P1 records have `entity_npi` set. The NPI is the sole lookup key. Probabilistic/ML matching (Splink) is deferred to Phase 3-I.
- **F1 (NPPES) as identity anchor.** When F1 is the first record for an NPI, full identity (name, entity_type, addresses, taxonomies, other_identifiers) is extracted. When F1 arrives for a bundle seeded by another source, it upgrades the primary identity fields. Prior stub primary_name is preserved as a name_variant if it differs and is non-trivial.
- **Source tier confidence model.** Four tiers determine confidence contribution:
  - Tier A (NPI-authoritative): F1 (NPPES) -- sets base confidence 0.950.
  - Tier B (NPI-corroborating, NPI always from raw): F4, I1, I2 -- +0.015 each.
  - Tier C (NPI-partial, NPI from raw OR entity_npi): F2 (OIG LEIE) -- +0.005.
  - Tier D (NPI-caller, NPI always from caller-supplied entity_npi): F3, A1, A2 -- +0.000.
  - F1 absent: max 0.750, human_review_required = True regardless of other sources.
  - Cap: min(score, 0.999). human_review_required: score < 0.850 (configurable).
- **Architecture target met.** F1 + F4 + I1 = 0.950 + 0.015 + 0.015 = **0.980 >= 0.98 architecture criterion** (architecture-lock.md: ">98% identity precision").
- **Idempotency.** Resolving a source_id already in contributing_sources returns ResolutionAction.SKIPPED (no-op). Guards against double-processing in Temporal at-least-once delivery.
- **Batch ordering.** `resolve_batch()` sorts F1 records first so the identity anchor is established before corroborating records are merged.
- **Non-F1 first records.** Minimal stub bundle (best-available name hint, entity_type=INDIVIDUAL default) with human_review_required=True. F1 arrival upgrades the bundle.
- **Name variant deduplication.** Normalized key `first.lower():last.lower()`. Original casing preserved in stored ProviderName. Address deduplication by (street_line_1.lower(), postal_code) tuple.
- **gender deferred.** NppesRecord does not yet carry a gender field (F1 normalizer does not extract basic.gender). UnifiedIdBundle.gender defaults to Gender.UNKNOWN in Phase 2-E. C13 (Entity Linking & Merge) adds gender extraction in Phase 2-F.
- **`model_copy(update=...)` pattern.** UnifiedIdBundle extends MedproBaseModel (mutable). Updates use Pydantic v2 `model_copy(update=...)` for clarity and testability.
- **`identity-test` Makefile target.** `.github/workflows/identity-validate.yml` CI. `identity` package added to pyproject.toml.

**Deferred / open:**
- Aurora-backed IdentityStore: `unified_id_bundles` table in migration 0001 is the target; deferred to Entry 003 (AWS account/region). Row-level `SELECT ... FOR UPDATE` concurrency lands with the Aurora path.
- Probabilistic/ML matching: Phase 3-I (Splink). Needed when state-board adapters add sources with partial NPI coverage.
- Gender extraction from F1 basic.gender: C13 Phase 2-F.
- Temporal worker concurrency: Phase 2-H wires these resolvers as Temporal activities.
- Per-NPI DB lock: replace in-memory store with Aurora upsert + row lock in Phase 2-H.

**Locked:** NPI-exact-match only (MVP), F1-anchor model, 4-tier confidence arithmetic, idempotency via source-ID dedup, batch F1-first ordering.

---

## Entry 027 -- Entity Linking & Merge MVP Design (C13, Phase 2-F)

**Date:** 2026-05-26
**Status:** Locked
**Author:** Claude (session 2026-05-26)

**Decision:** Build `src/entity_linker/` as a pure in-memory library that consumes a `UnifiedIdBundle` (C12 output) and all contributing `NormalizedRecord` objects for a given NPI, producing a `CanonicalProviderProfile` (schema v1). Four derived signals are computed per profile: `exclusion_flag`, `identity_confidence`, `specialty_classification`, `data_completeness`.

**Key design choices:**

- **Library pattern.** `src/entity_linker/` follows the same pattern as `src/normalizers/` and `src/identity/`: pure Python package, no network I/O, no DB writes, no side effects. Will become a Temporal activity in Phase 2-H.
- **Route by `record_type` discriminator.** Records are routed to per-type extractor functions via a `_BUCKET_MAP` dict keyed on `record_type` strings (not `isinstance` checks). Adding a Phase 3 record type (state board, court) requires one line in `_BUCKET_MAP` and a new extractor function -- no changes to existing code.
- **Extractors as pure functions.** Each extractor in `extractors.py` takes a `list[<Subtype>]` and returns profile sub-models. Stateless and independently testable.
- **`get_specialty_group()` via F1 normalizer.** Called on the first NppesRecord to resolve the specialty group string from the I4 NUCC taxonomy crosswalk. Result stored in `MergeResult.specialty_group` and in the `specialty_classification` DerivedSignalSummary. Not a standalone profile field (profile schema has `primary_specialty: TaxonomyCode`, not a string group).
- **Four derived signals always produced.** `exclusion_flag`, `identity_confidence`, `specialty_classification`, `data_completeness`. Signal types are a stable contract for the report renderer (C17). All four are emitted even when the relevant sources were not checked (confidence=0.0 signals the gap).
- **COMPLETENESS_WEIGHTS rubric.** Eight weighted sections (weights sum to 1.0): identity_anchor (0.30), exclusion_checked (0.20), medicare_status (0.15), address_present (0.10), hospital_affiliation (0.10), medicaid_status (0.08), publications_checked (0.04), clinical_trials_checked (0.03). Score is the sum of weights for populated sections.
- **`is_partial` logic.** True when `completeness_score < LINKER_COMPLETENESS_THRESHOLD_FOR_PARTIAL` (default 0.70) OR `bundle.human_review_required`. F1 + F2 + I1 + F4 = 0.75 is the minimum set that produces a non-partial profile with the default threshold.
- **Gender pass-through.** `profile.gender = bundle.gender`. NppesRecord does not carry gender (F1 normalizer deferred `basic.gender` extraction in Phase 2-D per Entry 025). `bundle.gender` is always `Gender.UNKNOWN` until C11 adds gender extraction. No change to that deferral here.
- **Medicare precedence.** I1 `participation_indicator` is authoritative for `accepts_medicare` and `opted_out_of_medicare`. CMS Care Compare (F4) `opted_out_of_medicare` flag is used as a fallback only when I1 is absent.
- **Hospital affiliation deduplication.** By `(hospital_name.lower(), hospital_pac_id)` key. CMS reports one row per NPI per practice address; the same hospital may appear in many rows for the same provider. Dedup prevents duplicate `HospitalAffiliation` entries.
- **Source coverage.** `SourceCoverage` entries grouped by `SourceCategory` (FEDERAL: F1-F4/I1/I2; ACADEMIC: A1/A2). MVP: `sources_attempted == sources_succeeded` (failed fetches are tracked in `SourceHealthRecord`, not here). Phase 2-H Temporal workflow will track attempted vs succeeded at the workflow level.
- **`report_disclaimer_required` always True.** Path B non-CRA constraint (DECISIONS.md Entry 006). Report generation (C17) must include the personal-research-only disclaimer on every report.
- **`MergeResult` wrapper.** Carries the profile + `RecordTypeCounts` (per-type input counts) + `merged_at` timestamp + `specialty_group` string. Metadata travels through the Temporal workflow (Phase 2-H) without being stored in the profile schema.
- **109 new tests.** `test_extractors.py` (per-extractor), `test_signals.py` (per-signal + COMPLETENESS_WEIGHTS invariants), `test_merger.py` (EntityLinker.build_profile combinations), `test_entity_linker_integration.py` (end-to-end). 885 total passing (7 deselected integration).
- **`entity-linker-test` Makefile target.** `.github/workflows/entity-linker-validate.yml` CI. `entity_linker` package added to pyproject.toml.

**Deferred / open:**
- Aurora persistence: `canonical_provider_profiles` table (migration 0001) is the target; deferred to Entry 003 (AWS account/region).
- State-board records (StateBoardLicenseRecord, StateBoardDisciplinaryRecord): Phase 3-A adds extractor functions and `_BUCKET_MAP` entries.
- Court records (CourtCaseRecord): Phase 3-C.
- Review platform records (ReviewPlatformRecord): Phase 3-E.
- Gender extraction from F1 `basic.gender`: requires C11 (NppesNormalizer) to add the field first. Deferred from both Entry 025 (C11) and Entry 026 (C12).
- A1/A2 `author_position` enrichment: deferred; `author_position` is None in C11 for all P1 records.
- `is_partial` lifecycle: Phase 2-H Temporal workflow will set `is_partial = False` when the full ingest cycle completes for a provider.

**Locked:** library pattern, `record_type` discriminator routing, four derived signals, COMPLETENESS_WEIGHTS rubric, Path B `report_disclaimer_required=True`, gender pass-through from bundle.

---

## Entry 028 -- Provider Search Service Design (C14, Phase 2-G)

**Date:** 2026-05-26
**Status:** Locked
**Author:** Claude (session 2026-05-26)

**Decision:** Build `src/search/` as a pure library plus `src/backend/search_service/` FastAPI shell (port 8003). The library converts `CanonicalProviderProfile` objects into OpenSearch documents and writes them to the `providers-{env}` index (template already shipped in Phase 1-C). The FastAPI shell exposes `GET /v1/providers/search`, `GET /v1/providers/{npi}`, and `POST /v1/providers/{npi}/index`.

**Key design choices:**

- **Library + service split.** `src/search/` (pure, no network I/O in isolation) vs `src/backend/search_service/` (FastAPI shell). Same pattern as `src/entity_linker/` + `src/backend/source_health_monitor/`. The library is independently testable with a mock client.
- **httpx over opensearch-py.** Avoids a new dependency; the REST API surface needed (PUT `/_doc/{id}`, POST `/_bulk`, POST `/_search`, GET `/_doc/{id}`) is small and stable.
- **NPI as document `_id`.** `PUT /{index}/_doc/{npi}` -- NPI is the system-wide unique key. `GET /v1/providers/{npi}` calls `client.get_doc()` (O(1) fetch), not a search query.
- **`build_provider_doc()` pure function.** Takes `CanonicalProviderProfile`, extracts the search-facet fields (name, states, cities, zips, specialty, flags, signals), and returns a `ProviderDoc`. All list fields sorted for deterministic output.
- **`build_search_query()` pure DSL builder.** `bool` query: `match_all` (no `q`) or `multi_match` (with `q`, `fuzziness=AUTO`, `operator=and`). Filter clauses for state, specialty_code, entity_type, has_exclusion, has_active_license. Wrapped in `function_score` with `field_value_factor` on `identity_confidence` (factor=1.5, boost_mode=multiply) to rank verified providers above partial stubs.
- **`_source` projection on all queries.** Only the 8 fields needed by `ProviderSearchHit` are returned, keeping payload size minimal.
- **`SearchSettings` env prefix `SEARCH_`.** Avoids collision with other service settings in local dev. `is_configured` returns False when `opensearch_url` is blank (default shell behavior pre-Entry 003).
- **`ProviderIndexer.index_batch()`.** Sends one bulk request for a list of profiles. Parses per-item errors when `errors=True`; returns `BatchIndexResult` with per-NPI failure list.
- **`report_count = 0` always.** The counter is not yet wired. Phase 2-J (Stripe + report pipeline) will increment it via Aurora query at index time.
- **`overall_risk_score = 0.0` default.** The `overall_risk_score` signal is not produced by C13; it is deferred to C16 (Phase 2-J Analytics & Anomaly Detection). `_get_signal_value()` returns 0.0 when the signal is absent.
- **108 new tests.** `test_document.py` (38 pure unit tests), `test_query.py` (28 DSL tests), `test_indexer.py` (22 mock-client tests), `test_search_service.py` (20 FastAPI TestClient tests). 993 total passing (7 deselected integration).
- **`search-test` Makefile target.** `.github/workflows/search-validate.yml` CI. `search` package added to pyproject.toml.

**Deferred / open:**
- Live OpenSearch cluster: Entry 003 (AWS account/region) must be resolved.
- Aurora `canonical_provider_profiles` read path: Phase 2-H Temporal workflow will call `ProviderIndexer.index_profile()` after each `EntityLinker.build_profile()` completes.
- `overall_risk_score` signal: Phase 2-J C16 Analytics & Anomaly Detection.
- `report_count` counter: Phase 2-J Stripe + report pipeline.
- Async client: deferred until Phase 2-H Temporal activity wiring requires it.
- Phase 2-K frontend integration: uses `GET /v1/providers/search` + `GET /v1/providers/{npi}`.

**Locked:** library pattern + service split, httpx over opensearch-py, NPI as `_id`, pure document builder, function_score identity_confidence boost, SEARCH_ env prefix, `is_configured` shell pattern.

---

## Entry 029 -- Temporal Workflow + Basic Report Generation Design (Phase 2-H)

**Date:** 2026-05-26
**Status:** Locked
**Author:** Claude (session 2026-05-26)

**Decision:** Phase 2-H ships two components: `src/workers/` (C15 basic -- Temporal worker) and `src/report/` (C17 basic -- report generation library + HTML renderer), plus a `src/backend/report_service/` FastAPI shell (port 8004).

**Key design choices:**

- **`src/workers/` library + worker entrypoint.** Six Temporal activity functions (`fetch_source_activity`, `normalize_records_activity`, `resolve_identity_activity`, `link_and_merge_activity`, `index_profile_activity`, `generate_report_activity`), each wrapping one Phase 2 pure library (C10-C17). `ProviderPipelineWorkflow` orchestrates all six in sequence with a parallel fan-out fetch step. Activities are plain Python functions decorated with `@activity.defn` -- testable without a live Temporal server.
- **Temporal `temporalio` Python SDK (v1.27).** `@workflow.defn` + `@workflow.run` pattern. `with workflow.unsafe.imports_passed_through()` for non-deterministic imports inside the workflow module. Retry policies: standard 3-attempt exponential backoff for all steps; `maximum_attempts=1` (best-effort) for OpenSearch index and, if needed, future non-critical steps.
- **NormalizedRecord subclass deserialisation.** Temporal serialises activity I/O as JSON. Roundtripping `NormalizedRecord` through JSON loses subclass type info. Fixed with a `_RECORD_TYPE_MAP` dict keyed on `record_type` discriminator string -- the link and resolve activities use it to reconstruct the correct subclass (e.g., `NppesRecord`) before passing to the entity linker.
- **`src/report/` pure library.** `build_report(profile) -> ProviderReport`: pure transform, no network I/O. `render_html(report) -> str`: Jinja2 autoescape on. `PATH_B_DISCLAIMER` constant always injected (DECISIONS.md Entry 007). `is_partial` propagates from `CanonicalProviderProfile`.
- **`ProviderReport` typed model.** Flat, JSON-serialisable Pydantic model. Sections: identity, addresses, licenses, exclusions, disciplinary, education, insurance, source coverage. `has_active_license`, `has_active_exclusion`, `has_active_discipline` booleans for fast UI flags.
- **`SourceCoverage` expansion.** `CanonicalProviderProfile.source_coverage` is category-level (one entry per `SourceCategory`). `_build_source_coverage()` expands it to per-source rows using `sources_attempted` + `sources_succeeded`/`sources_failed` membership checks.
- **Jinja2 HTML template.** `provider_report.html.j2`: self-contained (inline CSS), no external CDN. Status pills (active/revoked/suspended), alert banners for exclusions and disciplinary actions, partial report badge. `select_autoescape` for XSS protection. PDF (WeasyPrint) deferred to Phase 5-C.
- **`src/backend/report_service/` FastAPI shell (port 8004).** `POST /v1/reports/from-profile` (JSON) and `POST /v1/reports/from-profile/html`. Accepts a serialised `CanonicalProviderProfile` body, builds and returns a report synchronously. No persistence, no Temporal trigger (those wire in Phase 2-I+).
- **`P1_SOURCE_IDS` constant.** Worker config defines the canonical list of 9 P1 source IDs to attempt per pipeline run. Overridable per-workflow via `ProviderPipelineInput.source_ids`.
- **I4 static path.** `fetch_source_activity` returns `fetch_status="success"` with empty records for source `I4` (NPPES Taxonomy Crosswalk) -- it is a static in-process lookup handled by the normaliser, not a live fetch.
- **200 new tests.** `test_builder.py` (88 report library tests), `test_renderer.py` (30 HTML tests), `test_report_service.py` (22 FastAPI tests), `test_fetch_activity.py` (14 async activity tests), `test_normalize_activity.py` (21 tests), `test_resolve_activity.py` (16 tests), `test_link_activity.py` (16 tests), `test_index_activity.py` (14 tests), `test_generate_report_activity.py` (16 tests). 1193 total passing (7 deselected integration). Zero regressions.
- **`report-test` + `worker-test` + `run-report-service` + `run-worker` Makefile targets.** `report` + `workers` packages added to pyproject.toml.

**Deferred / open:**
- Live Temporal cluster: Entry 003 (AWS account/region). `WORKER_TEMPORAL_ADDRESS` must be set.
- `TEMPORAL_ADDRESS` + live Temporal workflow execution: Phase 2-H activities are wired and tested; end-to-end workflow execution deferred to when Entry 003 is resolved.
- PDF rendering (WeasyPrint): Phase 5-C.
- Report persistence (Aurora `reports` table): Phase 2-I.
- Temporal trigger from API gateway: Phase 2-I.
- `ProviderPipeline` async trigger endpoint (returns `report_id` for polling): Phase 2-I.

**Locked:** activity-per-library pattern, `_RECORD_TYPE_MAP` deserialiser for NormalizedRecord subclasses, PATH_B_DISCLAIMER always injected, SourceCoverage category-level to per-source expansion, Jinja2 autoescape, best-effort retry for index activity, WORKER_ env prefix.

---

## Entry 030 -- Report Generation MVP: Persistence + Temporal Trigger (Phase 2-I)

**Date:** 2026-05-26
**Status:** Locked
**Author:** Claude (session 2026-05-26)

**Decision:** Phase 2-I wires the report pipeline to Aurora persistence and adds a Temporal workflow trigger endpoint to the report service API.

**Key design choices:**

- **Migration 0005 (`0005_report_json_storage.py`).** Adds `report_json JSONB NULL` and `report_html TEXT NULL` to the `reports` table (inline storage; S3 is Phase 5-C). Makes `user_id` and `use_agreement_id` nullable for the pre-payment MVP phase (FKs retained -- NULL is valid, non-NULL must reference existing rows). Adds a GIN/btree index on `(report_json->>'npi')`. `tos_version_at_purchase` defaults to `"mvp-1.0"` for rows created by the API.
- **`ReportRepository` (sync SQLAlchemy).** Follows the audit service pattern: sync `create_engine`, no async ORM. Key operations: `create_row(npi, workflow_id?) -> UUID`, `set_workflow_id`, `mark_started`, `mark_complete(report_json, report_html, sources, is_partial)`, `mark_failed`, `get_row -> dict | None`. `is_configured` property guards all methods (raises `RuntimeError` if called with empty URL). HTML is silently truncated to NULL if it exceeds `html_max_bytes` (default 500 KB).
- **`persist_report_activity` (Phase 2-I Temporal activity).** New `@activity.defn(name="persist_report")` activity added to the worker. Takes `PersistReportInput(report_id: str, pipeline_result: dict)`. Deserialises `pipeline_result` as `ProviderPipelineResult`, calls `mark_complete` or `mark_failed` based on `pipeline_status`. Never raises -- all errors returned as `PersistReportOutput(persisted=False, error_message=...)`. DB not configured = `persisted=False` immediately. Registered in the worker entrypoint.
- **`ProviderPipelineWorkflow` step 7.** After `generate_report_activity`, if `inp.report_id` is set, the workflow calls `persist_report_activity` with `_BEST_EFFORT_RETRY` (maximum_attempts=1). Persistence failure does NOT fail the pipeline -- `ProviderPipelineResult` is returned regardless.
- **`ProviderPipelineInput.report_id` field.** New optional field (`str | None = None`). The API sets this to the DB row UUID before starting the workflow. Backward-compatible (defaults to None -- existing workflow tests pass without it).
- **`POST /v1/reports/request` endpoint.** Async FastAPI route. Steps: (1) validate NPI (10 digits), (2) generate `report_id = uuid4()`, (3) call `_repo.create_row(npi)` if DB configured, (4) call `_temporal_client.start_workflow(...)` if Temporal configured, (5) call `_repo.set_workflow_id(...)` if both succeeded. Returns `ReportRequestResponse(report_id, status="queued", npi, db_persisted, temporal_queued, message)`. Always returns 200 -- failures are reported as `db_persisted=False` / `temporal_queued=False` with a `message` field explaining what is unconfigured.
- **`GET /v1/reports/{report_id}` endpoint.** Sync FastAPI route. Returns 503 if `_repo` is None; 422 if `report_id` is not a valid UUID; 404 if not found. Returns `ReportStatusResponse` with full row data including `report` (dict) and `has_html` (bool).
- **Singleton injection pattern.** `_set_repo(repo)` and `_set_temporal_client(client)` module-level setters in routes.py. The app factory sets them in a `@app.on_event("startup")` handler (try/except -- safe if unconfigured). Test code can use `monkeypatch.setattr` to inject mock repositories.
- **`ReportServiceSettings` (REPORT_ env prefix).** `database_url` (REPORT_DATABASE_URL, falls back to DATABASE_URL via `model_post_init`), `temporal_address`, `temporal_namespace`, `temporal_task_queue`, `html_max_storage_bytes`. `is_db_configured` and `is_temporal_configured` guard properties.
- **65 new tests.** `test_persist_activity.py` (14 not-configured-path tests), `test_models.py` (35 model tests covering Phase 2-H + 2-I models), `test_report_service.py` additions (17 request/status endpoint tests + 2 monkeypatched mock-repo tests), `test_migrations.py` additions (7 0005 structural unit tests), `test_repository.py` (9 unit + 11 integration-marked). 1258 total passing (18 deselected integration). Zero regressions.

**Deferred / open:**
- Live Aurora DB: Entry 003 (AWS account/region). Integration tests in `test_repository.py` deselected.
- Live Temporal cluster: Entry 003. `REPORT_TEMPORAL_ADDRESS` must be set.
- HTML > 500 KB: stored as NULL; full S3 persistence is Phase 5-C.
- `user_id` / `use_agreement_id` re-enforced as NOT NULL: Phase 2-J (payment + auth flow).
- `tos_version_at_purchase = "mvp-1.0"` placeholder: Phase 2-J versioned agreement flow.

**Locked:** migration-0005 inline JSON storage, ReportRepository sync SQLAlchemy, persist_report best-effort in workflow, REPORT_ env prefix, `is_configured` gate pattern, POST /v1/reports/request always-200 with diagnostic fields.

---

## Entry 031 -- Payment Service MVP: Stripe Checkout Design (Phase 2-J)

**Date:** 2026-05-26
**Status:** Locked
**Author:** Claude (session 2026-05-26)

**Decision:** Phase 2-J builds `src/backend/payment_service/` (port 8005): Stripe Checkout session creation, webhook handler, PaymentRepository, and migration 0006.

**Key design choices:**

- **Stripe Checkout (not Payment Intents).** Stripe hosts the payment form -- zero PCI scope for the application. `POST /v1/payments/checkout` creates a Checkout session with `mode="payment"`; the client redirects the user to `checkout_url`. Simpler than Payment Intents for a one-time purchase MVP.
- **Migration 0006 adds two columns to `reports`:** `stripe_checkout_session_id VARCHAR(200) NULL` (partial unique index for O(1) webhook lookup) and `payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid'` (CHECK constraint: unpaid|pending|paid|refunded). Payment state is tracked separately from pipeline `status` -- a report can be `status='complete'` with `payment_status='unpaid'` (free tier / operator) or `payment_status='paid'` (standard consumer flow).
- **Session metadata carries `report_id`, `npi`, `certified_personal_use_only="true"`.** The webhook handler reads `report_id` from metadata (fallback for the case where `stripe_checkout_session_id` was not stored in the DB due to a transient error). Metadata is baked in at session creation time and is immutable.
- **`certified_personal_use_only` validated at checkout creation time.** The Pydantic `CheckoutRequest` model raises a 422 if the field is `False`. This is the Path B gate at the payment layer. The flag is stored in session metadata so the webhook can create the `use_agreements` row with `certified_personal_use_only=True`.
- **Use agreements created in the webhook handler.** The `use_agreements` row is written when `checkout.session.completed` fires (user has completed payment). `agreed_at` = webhook receipt time. `ip_address` = None (Stripe webhook IP; no user IP available). `user_agent = "Stripe/1.0 (webhook)"`. Phase 2-K will add a pre-checkout agreement endpoint that captures the real user IP.
- **User upsert by email (INSERT ON CONFLICT DO NOTHING).** The webhook creates a minimal `users` row from `session.customer_email` if one does not exist. `auth_provider_sub` is left NULL -- Phase 2-K links the Auth0 account. Email uniqueness constraint on `users` is the idempotency anchor.
- **Idempotent webhook handler.** Before processing `checkout.session.completed`, check `payment_status`. If already `'paid'`, return `action='skipped'` immediately. Prevents double-charging or double-creating use_agreements on Stripe retry.
- **Webhook signature verification fails hard (400).** `stripe.Webhook.construct_event()` raises `SignatureVerificationError` on bad signatures. Return 400 so Stripe knows the event was rejected and can retry with the same payload. Permanent 400s (invalid JSON, missing report_id) are also returned as 400.
- **DB errors in webhook return 200.** A RuntimeError inside the DB operations returns `action='error'` with status 200. This prevents Stripe from infinite retry of a fundamentally broken state. The event must be re-processed by an ops engineer via the Stripe dashboard event log.
- **Stripe not configured = graceful degradation.** When `PAYMENT_STRIPE_SECRET_KEY` is empty, `POST /v1/payments/checkout` returns a mock checkout URL with `stripe_configured=False`. The service starts and the health endpoints work without any Stripe credentials.
- **PAYMENT_ env prefix.** `PaymentServiceSettings` uses `PAYMENT_` to avoid collision. `PAYMENT_DATABASE_URL` falls back to `DATABASE_URL` (same pattern as `ReportServiceSettings`).
- **`stripe` Python SDK (v10+).** Added as a main dependency in `pyproject.toml`. Lazy-imported in routes.py (`_stripe_module()`) so the service can import and start even if stripe is not installed (returns None = unconfigured path).

**Deferred / open:**
- Live Aurora DB: Entry 003 (AWS account/region). Integration tests for PaymentRepository are not yet written.
- `user_id` / `use_agreement_id` NOT NULL constraint re-enforcement: Phase 2-K when auth is wired.
- `tos_version_at_purchase` on the reports row: currently `"mvp-1.0"` (set by ReportRepository at row creation). Phase 2-J sets `TOS_VERSION` on use_agreements; the reports row version placeholder is NOT updated here -- that alignment deferred to Phase 2-K when a versioned ToS flow lands.
- Phase 2-K: pre-checkout use-agreement endpoint that captures user IP + user_agent before Stripe redirect.
- Stripe Customer Portal (subscription management): Phase 5-G.
- Refund handling: Phase 5-G.

**Locked:** Stripe Checkout mode, session metadata for webhook lookup, migration-0006 column names + CHECK constraint, PAYMENT_ env prefix, idempotent webhook handler, DB errors = 200 in webhook, lazy stripe import pattern, PaymentRepository sync SQLAlchemy text() operations.

---

## Entry 032 -- Frontend Phase 1: Next.js App Router Design (Phase 2-K)

**Date:** 2026-05-26
**Status:** Locked
**Author:** Claude (session 2026-05-26)

**Decision:** Phase 2-K builds `src/frontend/` -- the Next.js 14 App Router frontend for researchyourdoctor.com. Covers Auth0 login, Path B certification gate, provider search, and report viewer with Stripe payment gate.

**Key design choices:**

- **Next.js 14 App Router (not Pages Router).** App Router is the current Next.js standard. Server Components reduce client bundle size; server-side getSession() for auth checks is cleaner than Pages Router getServerSideProps.
- **`@auth0/nextjs-auth0` v3.** App Router compatible. `handleAuth()` exports GET handler for the `[...auth0]` catch-all route. `getSession()` works in Server Components. `withMiddlewareAuthRequired()` for route protection in middleware.ts.
- **API Route proxy layer.** Browser never calls backend services directly. All calls go through `/api/*` Next.js routes which: (1) verify Auth0 session, (2) forward to the appropriate backend service with a request-id header, (3) return the response. This eliminates CORS configuration on the backend, keeps service URLs server-only, and provides a natural auth enforcement point.
- **Server-only env vars for backend URLs.** `SEARCH_SERVICE_URL`, `REPORT_SERVICE_URL`, `PAYMENT_SERVICE_URL` have no `NEXT_PUBLIC_` prefix -- they never reach the browser bundle. Defaults to localhost ports for local dev.
- **TanStack Query v5 for client-side fetching.** Used in search page (query enabled when query string non-empty) and ReportStatusPoller (refetchInterval stops when terminal status reached). `QueryProvider` wraps the app client-side. Server Components use direct fetch; client components use useQuery.
- **CSS Modules for styling.** No external UI library. Avoids introducing an unlocked dependency. Each component/page has a co-located `.module.css`. Global CSS variables defined in `globals.css` for color/spacing tokens.
- **Zod for runtime validation.** All API responses are parsed through Zod schemas at the proxy boundary. TypeScript types are inferred from schemas -- no manual interface duplication. `ApiError` class carries HTTP status for client-side error display.
- **Path B certification as session cookie.** The frontend shows a `/certify` page after login. Clicking "I Certify" sets a `medpro_path_b_certified` cookie client-side and redirects to `/search`. The legally binding `use_agreements` DB row is written at payment completion (Phase 2-J webhook), not at this UI step. The cookie gate is a UX mechanism, not a legal enforcement mechanism.
- **ReportStatusPoller.** TanStack Query `refetchInterval` polls GET /api/reports/{id} every 3 seconds until status is `complete` or `failed`. Once terminal, polling stops. Shows loading spinner during generation, PaymentGate for unpaid complete reports, ReportViewer for paid reports.
- **ReportViewer uses sandboxed iframe.** The report HTML (Jinja2-rendered from Phase 2-H) is rendered in an iframe with `sandbox="allow-same-origin"` to prevent report content from executing scripts or submitting forms in the parent page context.
- **PaymentGate calls checkout proxy.** `POST /api/payments/checkout` with `certified_personal_use_only: true` (always; user already passed the certify gate). On success, `window.location.href = checkout_url` redirects to Stripe. On failure, error is displayed inline. Stripe not configured (dev mode) returns a mock URL.
- **Port 3100.** Frontend dev server runs on :3100 (not :3000) to avoid collisions with other local services. AUTH0_BASE_URL must match in .env.local.
- **Jest + React Testing Library.** 35 tests across: Zod schema parsing (types.test.ts), SearchBar behavior, ProviderCard rendering/interaction, PaymentGate checkout flow, ReportViewer conditional rendering.

**Deferred / open:**
- Live deployment: Entry 003 (AWS EKS) + legal gate.
- Auth0 tenant creation: Entry 002 locked Auth0 as provider; tenant not yet provisioned.
- `/terms` page linked from certify page: stub (404) until legal copy is drafted.
- Stripe success/cancel return URL handling: after Stripe checkout, user is redirected back to the report page. The URL must be configured in the Stripe Checkout session (report service, Phase 2-J). Currently the payment service hardcodes a placeholder success URL -- Phase 5-G will wire this properly.
- `user_id` / `auth_provider_sub` linking: the webhook creates a `users` row by email with `auth_provider_sub = NULL`. Phase 2-K does not yet link the Auth0 `sub` claim to the DB user. This alignment is deferred to the next session.
- Auth0 JWT audience wiring: the frontend Auth0 app and the backend JWKS validation (Phase 1-F) use the same Auth0 tenant. The `AUTH0_AUDIENCE` env var must match between the two when the tenant is provisioned.

**Locked:** Next.js 14 App Router, @auth0/nextjs-auth0 v3, API Route proxy pattern, CSS Modules, TanStack Query v5, Zod schema validation, port 3100, Path B cookie gate, iframe sandbox for report HTML.

---

## Entry 033 -- Auth0 Sub Linking + Stripe Return URL Pattern (Phase 2-L)

**Date:** 2026-05-26
**Status:** Locked

### Auth0 Sub Linking: Server-to-Server Sync

**Decision:** Link Auth0 `sub` to the `users` table via a new `POST /v1/users/sync` endpoint in the payment service. Called server-to-server from the Next.js `afterCallback` hook after a successful Auth0 login. No JWT validation at this endpoint.

**Rationale:**
- The `auth_provider_sub` column already exists in migration 0001 with a unique index, but `upsert_user` (Phase 2-J) left it NULL because Auth0 sub is not available at webhook time (only email + payment intent).
- After login, the Next.js server process has both `email` and `sub` from the Auth0 session. It calls `POST /v1/users/sync` with these values.
- No JWT validation in the payment service for this endpoint: the call originates from the Next.js server process (not from the browser), so trust is enforced by network boundary -- not by a JWT. Adding JWT validation here would duplicate auth_service JWKS logic and create a circular dependency (auth service for login, payment service for user sync, both in the same request path).
- `link_auth_sub` is idempotent: UPDATE ... WHERE auth_provider_sub IS NULL -- no-op if sub already set.
- `afterCallback` is best-effort: catches all errors; login must never fail because the payment service is down.

### Stripe Return URL Injection at the Next.js Proxy Layer

**Decision:** Inject `success_url` and `cancel_url` server-side at the Next.js API Route proxy (`/api/payments/checkout/route.ts`), not from the client component.

**Rationale:**
- `CheckoutRequest` (Phase 2-J) requires `success_url` and `cancel_url` but the frontend's `createCheckout()` helper never sent them -- this was a live 422 bug.
- Injecting at the proxy layer keeps Stripe URL construction out of client-side code and ensures the URLs match the actual deployment environment without requiring additional env vars in the browser bundle.
- Pattern: `success_url = {appBase}/reports/{report_id}?session_id={CHECKOUT_SESSION_ID}` where `{CHECKOUT_SESSION_ID}` is a Stripe-native template variable substituted before the redirect.
- `appBase` is derived from `NEXT_PUBLIC_APP_URL` env var if set, otherwise from `req.headers.get("host")` with protocol inference (localhost = http, else https).

**Locked:** server-to-server sync via `/v1/users/sync`; no JWT in payment service for sync; afterCallback best-effort; proxy URL injection; `{CHECKOUT_SESSION_ID}` template variable.

---

## Entry 034 -- E2E Test Harness: Playwright + page.route() Mock Strategy (Phase 2-M)

**Date:** 2026-05-26
**Status:** Locked

### Why Playwright

- `@playwright/test` is the standard for Next.js App Router E2E testing (recommended by Vercel).
- Chromium-only in CI (fastest, most consistent); other browsers available locally.
- `storageState` for session simulation avoids fighting Next.js middleware.

### Why page.route() over MSW (Mock Service Worker)

- Next.js App Router uses Server Components that render on the server -- MSW service worker injection only intercepts client-side fetch, not server-side fetch in API Routes or Server Components.
- `page.route()` intercepts at the Playwright browser level, before any request leaves the test browser. This captures calls from both Client Components and Next.js API Routes (when the browser is the caller).
- Simpler dependency tree: no MSW install, no service worker setup, no Next.js worker config.

### Auth Mock Pattern

- Global setup (`setup/auth.setup.ts`) intercepts `/api/auth/me` and saves `storageState`.
- Specs inherit the auth state via Playwright project dependencies (`storageState: "playwright/.auth/user.json"`).
- Auth0 middleware (`withMiddlewareAuthRequired`) checks the Auth0 session cookie, not just `/api/auth/me`. In test context without a real Auth0 tenant, middleware may still redirect to the real Auth0 login URL. Specs are written defensively (accept redirect gracefully rather than failing).
- Full middleware mock requires a real Auth0 tenant or a custom middleware stub -- deferred until tenant is provisioned.

### Fixture JSON Strategy

- All fixture files match the Zod schemas in `src/lib/types.ts` structurally.
- `MockState.reportCallCount` simulates the `pending -> complete` polling transition without real waiting.

**Locked:** `@playwright/test ^1.44`, chromium-only in CI, `page.route()` intercepts, `storageState` auth pattern, fixture JSON in `tests/e2e/fixtures/`.
