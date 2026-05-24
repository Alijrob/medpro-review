# FCRA Architectural Blueprints — Medical Professionals Review

**Document Type:** Legal Counsel Reference — Architectural Input
**Status:** DRAFT — Awaiting Legal Determination
**Prepared:** 2026-05-24
**Phase:** 0-B
**Audience:** Legal counsel + product/engineering leads

> **Disclaimer:** This document is an architectural and product analysis prepared to support legal counsel in rendering a FCRA classification opinion. Nothing in this document constitutes legal advice. All FCRA determinations must be made by qualified legal counsel. Engineering shall not interpret this document as authorization to begin implementation of any code path.

---

## Purpose

This document presents two parallel architectural blueprints:

- **Path A — CRA Classification:** The platform is determined to be a Consumer Reporting Agency (CRA) under 15 U.S.C. § 1681a(f).
- **Path B — Non-CRA Classification:** The platform is determined to fall outside the FCRA's CRA definition.

Each blueprint describes the resulting architectural obligations, component-level deltas, estimated build impact, and data sourcing constraints. The goal is to give legal counsel a precise technical picture of what each determination requires, and to give engineering a pre-approved pivot plan so either outcome is executable without delay.

Legal counsel is asked to return a binding written opinion that answers the threshold questions in **Section 2** below and designates one of the two paths as operative.

---

## 1. Platform Description for Legal Review

Medical Professionals Review is a consumer-facing web platform. A user (a patient, caregiver, employer, or credentialer) pays a per-report or subscription fee to query a healthcare provider by name. The platform:

1. Receives the provider name + optional location from the user.
2. Fans out to 6+ data source categories (federal registries, state licensing boards, court records, commercial directories, review platforms, insurance networks).
3. Normalizes, deduplicates, and identity-resolves the collected records into a Canonical Provider Profile.
4. Applies derived signals (anomaly detection, risk scoring, confidence scoring).
5. Assembles and delivers an HTML + PDF report within approximately 10 minutes.

**What the report contains:**
- Verified licensure status, license number, states, specialties
- Disciplinary actions, board sanctions, malpractice flags
- DEA status, OIG LEIE exclusion, SAM.gov debarment
- Court records (PACER + state/county courts)
- Insurance network participation
- Review platform aggregation (Google, Yelp)
- Academic publications and Doximity profile data
- Derived confidence score and risk flags with explanations

**Who the "consumer" is:** The healthcare provider is the natural person the report is about. The paying user is the requestor.

**Intended use cases at product launch:**
- Patients choosing a provider
- Caregivers researching on behalf of a patient
- Employers screening clinical staff (credential verification)
- Credentialing organizations (hospitals, insurers, managed care organizations)

> ⚠️ The employment and credentialing use cases are the primary FCRA risk vectors. See Section 2.

---

## 2. Threshold Questions for Legal Counsel

Legal counsel's written opinion must address each question. Engineering will implement the path corresponding to the answers.

| # | Question | Operative Path |
|---|----------|---------------|
| Q1 | Does the platform, as described in Section 1, constitute a "consumer reporting agency" under 15 U.S.C. § 1681a(f) by reason of assembling or evaluating information on consumers for the purpose of furnishing consumer reports to third parties? | Q1=Yes → Path A; Q1=No → Path B |
| Q2 | If the platform currently falls outside the CRA definition, does offering access to employment or credentialing use cases change that determination? | Q2=Yes → Path A with use-case restriction, or Path A full |
| Q3 | Can the platform offer a "general information only / not for FCRA purposes" product tier that is credibly non-CRA, while offering a separate FCRA-compliant tier? | Q3=Yes → Dual-tier architecture (see Section 5) |
| Q4 | Are any of the planned data sources (PACER, state court records, commercial directories, review APIs) subject to independent restrictions that apply regardless of FCRA classification? | Answer informs Section 3 / Section 4 data source tables |
| Q5 | Does the platform's derived scoring (risk flags, anomaly signals) constitute an "evaluative" function that independently triggers CRA status even if raw data aggregation alone would not? | Q5=Yes → Path A regardless of other answers |

---

## 3. Path A — CRA Classification

### 3.1 What CRA Status Means

If the platform is a CRA, it is subject to the full obligations of the Fair Credit Reporting Act (15 U.S.C. § 1681 et seq.). These obligations apply to every consumer report issued and every system that produces, stores, transmits, or audits them.

Key statutory obligations triggered by CRA status:

| Obligation | Statute | Architectural Trigger |
|------------|---------|----------------------|
| Permissible purpose enforcement | § 1681b | Every report request must verify and log a legally permissible purpose before data is assembled |
| Maximum possible accuracy | § 1681e(b) | All source data must be accuracy-validated; procedures documented |
| Consumer file disclosure | § 1681g | Any provider must be able to request and receive a copy of their file |
| Dispute reinvestigation | § 1681i | Any disputed item must be reinvestigated within 30 days; verified, corrected, or deleted |
| Obsolescence / staleness | § 1681c | Most adverse information older than 7 years must be suppressed; no lookback beyond 10 years for bankruptcies |
| Adverse action notice | § 1681m | If a user takes adverse action against a provider based on the report, they must notify the provider |
| Disclosure of sources | § 1681g(a)(2) | Upon consumer request, sources of information must be disclosed |
| Security & data handling | FTC / CFPB guidance | Data must be secured; limited to permissible purpose transactions |
| Accuracy certification from users | § 1681e(a) | Users must certify their permissible purpose before receiving a report |

### 3.2 Architectural Obligations Under Path A

#### 3.2.1 Permissible Purpose Gate (C2 + C8)

Every report request must pass through a permissible-purpose verification step before any data assembly begins. This is an OPA policy enforced at the API gateway level.

**Required policy logic:**
- User must select a permissible purpose at checkout (employment screening, personal use, credentialing, insurance underwriting, or other § 1681b purpose).
- Purpose is logged immutably at request initiation (QLDB, C23).
- OPA (C2) enforces which data sources and derived signals are permitted for each purpose.
- Requests with no logged purpose are rejected before any data collection begins.
- Users must sign a certification affirming permissible purpose on account creation and at each report purchase.

**Schema addition (C6):**
```
PermissiblePurpose {
  purpose_code: enum [employment, credentialing, insurance, personal_use, other_1681b]
  user_certified_at: timestamp
  user_ip: string (hashed)
  report_id: uuid
  qldb_sequence_number: string
}
```

#### 3.2.2 Consumer File Disclosure Endpoint (C8 + C13 + C17)

The healthcare provider named in a report must be able to:
1. Submit a written request (via a provider portal or secure form) to view all information the platform holds about them.
2. Receive a complete disclosure within a legally defined window (§ 1681g: "clearly and accurately" disclosed, no fee in most circumstances).

**Required components:**
- Provider identity verification flow (not conflated with user auth — the subject accessing their file is a different party than the paying user).
- A "provider file view" report variant in C17 that renders all stored NormalizedRecords and their provenance.
- A secure, logged delivery channel (not the standard report viewer — access must be restricted to the verified subject).
- All disclosures logged to QLDB (C23).

#### 3.2.3 Dispute Workflow — FCRA-Grade (C20)

Under CRA status, disputes are governed by § 1681i. This is significantly more rigorous than a voluntary accuracy correction process.

**Statutory requirements baked into C20:**
- 30-calendar-day reinvestigation window (starts when dispute is received in writing, not when triaged).
- Platform must promptly notify the original source of the disputed information.
- If information cannot be verified, it must be deleted from the consumer's file and suppressed from future reports.
- Revised report must be sent free of charge to the consumer upon request.
- Consumer has the right to add a 100-word statement of dispute to their file if reinvestigation does not resolve the dispute.
- All dispute actions logged immutably in QLDB.
- Dispute record retention: minimum 2 years post-close per FTC guidance.

**C20 build delta vs. non-CRA baseline:**
- Hard 30-day SLA enforcement with escalation automation (Temporal workflow, not just a ticket).
- Source notification workflow: C10/C9 must support a "notify source of dispute" action.
- Dispute statement storage and attachment to future reports.
- Free revised-report issuance flow (bypass payment gate for dispute-triggered reissuance).

#### 3.2.4 Obsolescence Rules — Data Suppression (C2 + C11 + C25)

FCRA § 1681c prohibits reporting most adverse information older than 7 years. This requires:

- Every NormalizedRecord must carry a `record_date` (the date the underlying event occurred, not ingestion date).
- OPA policy (C2) must enforce suppression of records exceeding the obsolescence window before they reach the Canonical Provider Profile or any report.
- Court records, disciplinary actions, malpractice verdicts, and sanctions are the primary affected record types.
- Suppression must be applied at report generation time (C17), not only at ingestion — stale records should not be purged from raw storage but must not appear in consumer-facing output.
- Obsolescence logic must be auditable: suppression decisions logged to QLDB.

**Exception:** Bankruptcy (10-year window), and several categories that have no obsolescence limit (e.g., criminal convictions for crimes punishable by imprisonment for more than one year — legal counsel must confirm which provider-record types fall into which category).

#### 3.2.5 Adverse Action Notice Support (C17 + C22)

The platform cannot directly send adverse action notices — that obligation falls on the user who took the adverse action. However, the platform must:

- Provide users with a clear, pre-formatted adverse action notice template in their account panel and at report delivery.
- Include statutory contact information for the platform (as the CRA) so that the subject provider can request their file.
- Include the CFPB's consumer rights summary ("A Summary of Your Rights Under the Fair Credit Reporting Act") in every report.
- Log that an adverse action notice template was delivered to the user (for audit purposes).

#### 3.2.6 Data Source Restrictions Under Path A

| Source | Status Under CRA Path | Notes |
|--------|-----------------------|-------|
| NPPES (NPI Registry) | ✅ Permissible | Federal public registry |
| OIG LEIE | ✅ Permissible | Federal exclusion database |
| SAM.gov | ✅ Permissible | Federal debarment database |
| State licensing boards | ✅ Permissible | Public licensing data |
| PACER (federal court) | ⚠️ Legal review required | Court records permissible in many contexts; must confirm FCRA compatibility with counsel |
| State/county court records | ⚠️ Legal review required | Varies by state; some states restrict re-reporting of expunged records |
| Ribbon Health / Healthgrades / Vitals | ⚠️ Confirm ToS for CRA use | Commercial directories — ToS may prohibit CRA use of their data |
| Google Places / Yelp review APIs | ⚠️ Confirm ToS for CRA use | Review APIs — ToS may prohibit use in consumer reports |
| PubMed | ✅ Permissible | Public academic database |
| Doximity | ⚠️ Confirm ToS | Professional network — verify CRA use is permissible |
| Insurance network directories | ⚠️ Confirm with data provider | Licensed data — verify CRA use clause in contracts |

**Obsolescence filter applies to:** Court records, disciplinary actions, malpractice flags, sanction records.
**Obsolescence filter does NOT apply to:** Current licensure status, current OIG/SAM exclusion, NPI registry data.

#### 3.2.7 Estimated Build Impact — Path A vs. Baseline

| Component | Baseline Effort | CRA Delta | Notes |
|-----------|----------------|-----------|-------|
| C2 — OPA | 9 wk | +3 wk | Permissible purpose policies, obsolescence enforcement, source suppression |
| C6 — Schema | 8 wk | +1 wk | PermissiblePurpose entity, record_date on all NormalizedRecords, dispute statement field |
| C8 — API Gateway | 9 wk | +2 wk | Permissible purpose gate at request initiation |
| C13 — Entity Linking | 13 wk | +2 wk | Provider file view support; subject identity verification flow |
| C17 — Report Generation | 11 wk | +3 wk | CRA disclosure report variant, adverse action notice template, CFPB rights insert |
| C20 — Dispute Workflow | 12 wk | +5 wk | Hard 30-day Temporal SLA, source notification, statement storage, free reissuance |
| C22 — Notifications | 7 wk | +1 wk | Adverse action notice delivery; dispute acknowledgment to subject |
| C23 — QLDB Audit | 7 wk | +2 wk | Permissible purpose logs, disclosure logs, dispute action logs |
| **Total CRA delta** | | **~+19 wk** | Spread across Phases 2-5; does not extend Phase 6 |

> Note: The +19-week estimate assumes the CRA obligation is known before Phase 1 Foundations begins. If the determination arrives mid-build, rework cost increases significantly.

---

## 4. Path B — Non-CRA Classification

### 4.1 What Non-CRA Status Means

If the platform is not a CRA, the FCRA's CRA-specific obligations (§§ 1681b, 1681c, 1681e, 1681g, 1681i, 1681m) do not apply by statute. However:

- The platform is still subject to **state privacy laws** (CCPA/CPRA in California, and equivalent laws in other states).
- The platform is still subject to **defamation and tortious interference risk** if inaccurate reports harm a provider's reputation or livelihood — accuracy safeguards remain essential.
- The platform may still voluntarily adopt dispute and correction procedures for risk management and consumer trust.
- **HIPAA does not apply** to publicly reported data about providers (licensure, disciplinary actions) — HIPAA governs patient health information, not provider credential records.
- **Use-case restrictions must be enforced via ToS**, not FCRA: if the platform is non-CRA, users must contractually agree they are not using the report for employment, credit, insurance, or housing decisions. ToS enforcement is weaker than statutory enforcement — legal counsel should assess residual risk.

### 4.2 Permitted and Prohibited Conduct Under Path B

| Activity | Path B Status | Notes |
|----------|--------------|-------|
| Selling reports to patients for personal use | ✅ Permitted | Core use case; no FCRA hook |
| Selling reports to caregivers | ✅ Permitted | Same as personal use |
| Selling reports to employers for employment decisions | ❌ Prohibited (ToS restriction) | If permitted, re-triggers CRA question; counsel must confirm |
| Selling reports to credentialing organizations | ⚠️ Restricted via ToS | Legal counsel must define what "credentialing" use is permissible without triggering CRA status |
| Aggregating public court records | ✅ Permitted with care | State expungement laws still apply |
| Derived risk scoring (anomaly, risk flags) | ✅ Permitted with accuracy obligations | Still creates defamation/tortious interference risk if inaccurate |
| Data retention indefinitely | ✅ No FCRA limit | State law limits may apply (CCPA deletion rights) |

### 4.3 Remaining Architectural Obligations Under Path B

Even without CRA status, the following must be built to manage legal and reputational risk:

#### 4.3.1 Accuracy Safeguards (C25 + C11 + C2)

Non-CRA does not mean non-accountable. Reports that falsely attribute disciplinary actions, criminal records, or exclusions to the wrong provider create significant tort exposure.

**Required:**
- Data Quality Service (C25) with confidence scoring on all records.
- Identity resolution precision target (>98%) maintained regardless of FCRA status.
- Report disclaimer language: clear statement that the report is for informational purposes, not for employment or credit decisions.
- Mechanism for providers to submit corrections (voluntary, not statutory — but essential for liability management).

#### 4.3.2 Voluntary Dispute / Correction Process (C20 — simplified)

Without FCRA, the 30-day reinvestigation mandate does not apply. However, a correction process should still exist:

- Provider submits a correction request via web form.
- Internal team reviews within a defined SLA (recommend 15 business days for voluntary process).
- If correction is valid, record is updated and a corrected report is made available.
- No obligation to notify original source, but best practice to do so.
- QLDB audit trail still recommended for liability management.

**C20 build delta vs. CRA baseline:**
- No hard statutory SLA — Temporal workflow with configurable business-day SLA.
- No source notification workflow required.
- No free revised-report obligation.
- No dispute statement storage.
- Estimated effort: **~7 weeks** vs. 17 weeks under Path A.

#### 4.3.3 Use-Case Enforcement (C8 + C2 + C19)

If the platform is non-CRA, it must affirmatively prevent FCRA-triggering use cases through contractual and technical controls:

- At account creation: users certify they are not using reports for employment, credit, insurance, or housing decisions (ToS checkbox, logged in QLDB).
- At report purchase: purpose is selected; employment and credentialing purposes are either blocked or surfaced with a strong warning and additional ToS acknowledgment.
- OPA policy (C2): employment/credentialing purpose codes result in a warning interstitial and additional certification requirement, or are blocked entirely pending legal guidance.

> ⚠️ Legal counsel: please advise whether offering employment/credentialing use cases under ToS restriction (without FCRA compliance) is a viable risk posture, or whether those use cases must be completely excluded from the non-CRA product.

#### 4.3.4 State Privacy Law Compliance (C2 + C19 + C23)

CCPA/CPRA and equivalent state laws may give providers (as California residents) the right to:
- Know what data the platform holds about them.
- Request deletion of personal information.
- Opt out of sale of personal information.

**Required regardless of FCRA path:**
- Privacy policy covering all data categories collected.
- "Do Not Sell" mechanism (if platform data is licensed or resold to third parties).
- Data subject access request (DSAR) workflow — similar to CRA file disclosure but governed by state law, not FCRA.
- Deletion capability: ability to purge a provider's PII from NormalizedRecords and Canonical Profile upon verified request.

#### 4.3.5 Data Source Restrictions Under Path B

| Source | Status Under Non-CRA Path | Notes |
|--------|-----------------------------|-------|
| NPPES (NPI Registry) | ✅ Permissible | Federal public registry |
| OIG LEIE | ✅ Permissible | Federal exclusion database |
| SAM.gov | ✅ Permissible | Federal debarment database |
| State licensing boards | ✅ Permissible | Public licensing data |
| PACER (federal court) | ✅ Generally permissible | Court records are public; PACER ToS compliance required |
| State/county court records | ⚠️ State-by-state review | Expungement laws vary; must not surface sealed/expunged records |
| Ribbon Health / Healthgrades / Vitals | ⚠️ Confirm ToS | Non-CRA use may be permitted where CRA use was restricted |
| Google Places / Yelp review APIs | ⚠️ Confirm ToS | Review API ToS typically permits aggregation for informational use |
| PubMed | ✅ Permissible | Public academic database |
| Doximity | ⚠️ Confirm ToS | Professional network — verify informational use is permitted |
| Insurance network directories | ⚠️ Confirm with data provider | Licensed data — verify non-CRA informational use clause |

**No obsolescence filter required under Path B** (7-year FCRA rule does not apply). However, stale records should be flagged with age for accuracy/trust reasons.

#### 4.3.6 Estimated Build Effort — Path B

| Component | Estimated Effort | Notes vs. Path A |
|-----------|-----------------|------------------|
| C2 — OPA | 9 wk | Simpler: no permissible purpose enforcement; use-case gate only |
| C6 — Schema | 8 wk | No PermissiblePurpose entity required; record_date still recommended |
| C8 — API Gateway | 9 wk | No statutory permissible purpose gate |
| C13 — Entity Linking | 13 wk | No CRA file disclosure variant needed; DSAR flow instead |
| C17 — Report Generation | 11 wk | No CFPB rights insert; no adverse action template |
| C20 — Dispute Workflow | 7 wk | Simplified voluntary process; ~10 weeks saved vs. Path A |
| C22 — Notifications | 7 wk | No adverse action delivery |
| C23 — QLDB Audit | 7 wk | Reduced scope; use-case certification log only |
| **Total** | **~71 wk core** | **~19 weeks less than Path A** |

---

## 5. Dual-Tier Architecture (If Q3 = Yes)

If legal counsel determines that a credible dual-tier model is viable, the platform can offer:

**Tier 1 — Informational ("General Research"):** Non-CRA. Patient/caregiver use only. No employment or credentialing use permitted. Lighter compliance stack. Lower price point.

**Tier 2 — FCRA-Compliant ("Professional / Credentialing"):** Full CRA compliance. Employment, credentialing, and insurance use permitted. Full permissible purpose gate, 30-day dispute rights, adverse action notice support, CFPB disclosures. Higher price point.

**Architectural implication:** Both tiers share the data ingestion and identity resolution pipeline (C9-C13). The compliance layer (C2 OPA policies, C17 report variants, C20 dispute workflows, C23 audit logs) branches at the report request level. This is architecturally clean but adds approximately 8 weeks to C2 and C17 for dual-mode support.

**Legal requirement for dual-tier viability:** Counsel must confirm that Tier 1 reports can be reliably ring-fenced from FCRA-triggering use, and that the platform's ToS enforcement is sufficient to maintain the separation. If the ring-fence is not legally credible, the dual-tier model collapses to Path A.

---

## 6. Architecture Delta Summary

| Dimension | Path A (CRA) | Path B (Non-CRA) |
|-----------|-------------|-----------------|
| Permissible purpose gate | ✅ Statutory, hard-enforced | ⬜ ToS only, soft-enforced |
| Consumer file disclosure | ✅ Required (§ 1681g) | ⬜ DSAR only (state law) |
| Dispute reinvestigation SLA | ✅ 30 calendar days (statutory) | ⬜ Voluntary SLA (recommend 15 bus. days) |
| Adverse action notice support | ✅ Required | ❌ Not required |
| CFPB rights disclosure | ✅ Required in every report | ❌ Not required |
| Obsolescence / 7-year suppression | ✅ Required | ❌ Not required |
| Source notification on dispute | ✅ Required | ❌ Not required |
| Accuracy obligation | ✅ "Maximum possible accuracy" (§ 1681e) | ⚠️ Tortious interference standard (lower but non-zero) |
| State privacy law (CCPA etc.) | ✅ Required | ✅ Required |
| Employment/credentialing use | ✅ Permitted with full compliance | ⚠️ Restricted or prohibited |
| Additional build vs. baseline | +19 weeks | Baseline |
| OPA policy complexity | High | Moderate |
| C20 Dispute complexity | High (statutory) | Low (voluntary) |
| QLDB audit scope | Broad (every disclosure) | Narrow (certifications only) |

---

## 7. Questions for Legal Counsel

In addition to the threshold questions in Section 2, engineering requests counsel's written guidance on:

1. **Court records:** Which specific record types from PACER and state courts are reportable, and which are subject to obsolescence or suppression (e.g., sealed records, expunged convictions, juvenile records)? Under which path?

2. **Derived scoring:** The platform produces derived risk signals and anomaly flags with natural-language explanations. Does generating these signals constitute "evaluation" under § 1681a(f) even if the underlying data is public? (Relevant to Q5.)

3. **Employment vs. credentialing distinction:** Hospital credentialing organizations and managed care organizations review provider credentials for privileging purposes. Is this "employment" under FCRA? Is it a separate permissible purpose?

4. **Commercial data provider ToS for CRA use:** Several planned data sources (Ribbon Health, Healthgrades, Vitals, Doximity) are commercial. Under Path A, we need confirmation that our data licensing agreements explicitly permit CRA use. Can counsel advise on what language to require?

5. **State-specific restrictions:** Are there states where healthcare provider licensing data, disciplinary records, or court records have independent restrictions that require state-by-state compliance mapping (beyond FCRA)?

6. **Safe harbor vs. strict liability:** Under Path A, does § 1681n strict liability apply to willful violations only, and what constitutes reasonable procedures under § 1681e(b) for a platform of this type?

7. **Adverse action notice mechanics under Path B:** If a user takes adverse action against a provider using a Path B (non-CRA) report and does not provide an adverse action notice, does the platform bear any secondary liability?

---

## 8. Legal Gate Closure Criteria

Phase 0 closes and Phase 1 may begin when ALL of the following are in hand:

- [ ] Written binding legal opinion designating Path A or Path B (or Dual-Tier)
- [ ] Written answers to all Q1–Q5 threshold questions (Section 2)
- [ ] Written answers to Q1–Q7 supplemental questions (Section 7) or written acknowledgment that specific questions are out of scope
- [ ] For Path A: written approval of the permissible purpose taxonomy (Section 3.2.1 purpose codes)
- [ ] For Path A: written confirmation of which data sources are permissible for CRA use (Section 3.2.6 table)
- [ ] For Path B: written confirmation of which use cases are permissible without FCRA compliance
- [ ] Legal Gate Closure Document signed by legal counsel and product lead
- [ ] Compliance Architecture Specification (CAS) approved — C1 deliverable

Once the Legal Gate Closure Document is signed, engineering will designate the operative path in `DECISIONS.md` Entry 001 and begin Phase 1 Foundations.

---

## 9. Open Items Pending Legal Determination

| Item | Blocks | Owner |
|------|--------|-------|
| FCRA path designation (A / B / Dual) | Phase 1 start | Legal counsel |
| Permissible purpose taxonomy approval | C2, C8, C23 design | Legal counsel |
| Data source ToS for CRA use | C10 Source Adapter contracts | Legal + Product |
| Court record reportability matrix | C11 Normalization rules | Legal counsel |
| State-specific restriction map | C10 adapter config | Legal counsel |
| Auth0 vs. Okta selection | C7 | Engineering (see DECISIONS.md Entry 002) |
| AWS account / region / domain | C3 | Product/Operations (see DECISIONS.md Entry 003) |

---

*This document will be versioned as `fcra-blueprints-v1.md` upon legal determination. Path not taken will be archived as `fcra-blueprints-[path]-archived.md` for audit purposes.*
