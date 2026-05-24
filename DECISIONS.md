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

## Entry 002 — Auth0 vs. Okta: Unresolved

**Date:** 2026-05-24
**Status:** UNRESOLVED — architecture says "Auth0/Okta." Final selection must be locked before Phase 1-F.
**Impact:** SDK choice differs: `nextjs-auth0` vs. `@okta/okta-react`. Delay resolution past Phase 1-F start is a blocker.

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

**Open sub-item (Unresolved):** **Sentry SaaS vs. self-hosted** is not yet decided. SaaS is faster to operate but sends error payloads off-cluster — a data-residency consideration for regulated healthcare-adjacent data. Self-hosted keeps everything in-VPC at higher ops cost. PII scrubbing is mandatory either way and is already implemented. Must be decided before Sentry is actually wired (Phase 1-F, when services exist).

**Impact:** Phase 1-D config is complete and validated. Deployment waits on Entry 003 (AWS account/region) and the Phase 1-E GitOps layer.
**Locked:** Topology yes; Sentry hosting mode no.

---

<!-- Add new entries below this line -->
