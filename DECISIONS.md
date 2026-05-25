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

<!-- Add new entries below this line -->
