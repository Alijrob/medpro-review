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

<!-- Add new entries below this line -->
