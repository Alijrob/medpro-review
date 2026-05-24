# Source Priority Matrix — Medical Professionals Review

**Document Type:** Engineering Sequencing Reference
**Status:** DRAFT — Phase 0-D
**Prepared:** 2026-05-24
**Depends on:** `docs/reference/tos-matrix.md` (Phase 0-C)
**Drives:** Phase 2 and Phase 3 adapter build sequence
**Phase:** 0-D

> **Scope:** This document assigns a Priority Tier (P1/P2/P3) to every source in the ToS Analysis Matrix. It does not override legal sign-off requirements. No adapter may be built on any source — regardless of its priority tier here — until the main legal gate (Phase 0 FCRA determination) is closed and individual source counsel confirmation is obtained.

---

## 1. Scoring Rubric

Each source is evaluated on three independent dimensions, then assigned a priority tier.

### 1.1 Report Value (V) — 1 to 5

How much does this source improve report quality, differentiation, or consumer trust?

| Score | Meaning |
|-------|---------|
| **5** | Foundation-level: report is incomplete or unreliable without it |
| **4** | High value: meaningful signal, clearly improves report; noticeable absence |
| **3** | Medium value: useful signal but substitutable or narrow in scope |
| **2** | Low value: marginal improvement; narrow provider subset or weak signal |
| **1** | Minimal value: derivative signal, duplicates another source, or extremely narrow |

### 1.2 Integration Effort (E) — 1 to 5

How complex is it to build and maintain a production-grade adapter for this source?

| Score | Meaning |
|-------|---------|
| **1** | Trivial: documented public API or bulk download, clean data format, stable schema |
| **2** | Low: public API with key or simple bulk file; minor normalization required |
| **3** | Moderate: FOIA pipeline required, or web scraping of a structured portal, or third-party API with rate limits and schema drift risk |
| **4** | High: multi-step acquisition (FOIA + scrape + normalization), or B2B contract + custom integration, or fee-per-query economics |
| **5** | Very high: manual processes, no automation path, or county-by-county coverage requiring 50+ separate integrations |

### 1.3 Legal Clearance Required (L) — beyond the main Phase 0 legal gate

| Level | Meaning |
|-------|---------|
| **L0** | No additional clearance needed beyond main legal gate (CC0 / explicit public domain) |
| **L1** | Counsel confirmation of FOIA data in consumer reports + ToS review of bulk/API access |
| **L2** | Negotiated data license required (T3); must include explicit CRA use clause if Path A |
| **L3** | T4: likely prohibited under standard ToS; requires either (a) enterprise contract negotiation or (b) formal architectural removal decision before build can be scoped |

### 1.4 Priority Tier Assignment

| Tier | Criteria |
|------|----------|
| **P1 — Build first** | V ≥ 4 AND E ≤ 2 AND L = L0. Core federal open-data sources. Build immediately after legal gate closes (post-counsel confirmation of T1 status). |
| **P2 — Build second** | V ≥ 3 AND E ≤ 3 AND L ≤ L1. High-value FOIA/API sources where clearance is likely but requires explicit confirmation. Build after P1 adapters are stable and counsel has confirmed FOIA path. |
| **P3 — Contract/legal gate** | L ≥ L2, OR V < 3, OR E ≥ 4 for a marginal signal. Build only after the specific additional clearance is obtained. Low-value sources may not be built at all. |

---

## 2. Priority Tier 1 — Build First (Post-Legal-Gate)

**Gate:** Phase 0 legal gate closed + counsel confirms T1 status for each source.
**Target phase:** Phase 2-B (Federal Source Adapters), Phase 2-J (partial: Medicare participation), Phase 3-G (academic signals).

These are all T1 federal open-data sources: CC0 or explicit public domain, API-Free or Bulk-DL, documented stable schema, no contract required. They form the core identity and exclusion foundation of every report.

| ID | Source | V | E | L | Priority | Notes |
|----|--------|---|---|---|----------|-------|
| F1 | NPPES / NPI Registry (CMS) | 5 | 1 | L0 | **P1 — #1** | Single most important source. Every licensed US physician has an NPI. Provides identity anchor (NPI), specialty, address, taxonomy. All downstream identity resolution (C2-C5) depends on NPPES as the primary key. Build the NPI bulk-download adapter first. |
| F2 | OIG LEIE (HHS) | 5 | 1 | L0 | **P1 — #2** | Hard exclusion signal. A provider on the LEIE exclusion list cannot be paid by federal programs. Absence on LEIE is a required verification for any credentialing-adjacent report. Monthly bulk CSV + API. Highest V/E ratio after NPPES. |
| F3 | SAM.gov — Exclusions (GSA) | 4 | 1 | L0 | **P1 — #3** | Federal debarment list. Overlaps with LEIE for healthcare providers but extends to all federal contractors. Free API key, CC0 data. Important for completeness; some providers appear on SAM but not LEIE. |
| F4 | CMS Care Compare / Provider Data | 5 | 1 | L0 | **P1 — #4** | Medicare participation, quality measures, hospital affiliations. CC0, data.cms.gov REST API. Provides affiliation graph, accepts-assignment flag, and practice location data. Critical for report breadth. |
| I1 | CMS Medicare Physician Enrollment | 4 | 1 | L0 | **P1 — #5** | Medicare participation and opt-out status. CC0. Partial overlap with F4 but the enrollment file includes the opt-out list which is a high-value red flag signal. Bulk download available. |
| I2 | CMS Medicaid Provider Enrollment | 3 | 1 | L0 | **P1 — #6** | Medicaid participation by state. CC0. Lower individual provider value than Medicare data but adds coverage signal for primary care and pediatric providers. Bulk download available. Slightly lower V than I1; build with I1 batch. |
| I4 | NPPES NPI + CMS Specialty Crosswalk | 3 | 1 | L0 | **P1 — #7** | Derived signal — taxonomy codes from NPPES crosswalk to specialty groups. Used in C8 normalization layer to infer specialty category when no direct specialty data is available. Build as part of the NPPES adapter (no separate adapter needed). |
| A1 | PubMed / NCBI Entrez API | 3 | 2 | L0 | **P1 — #8** | NIH public domain. Identifies research-active physicians; publication count, affiliation, clinical trial authorship. Entrez API is stable and well-documented. Builds into C5 (entity enrichment). Lower V for general practitioners; higher V for academic medical centers. |
| A2 | ClinicalTrials.gov (NIH) | 2 | 1 | L0 | **P1 — #9** | Public domain. Investigator-level records for clinical trials. Narrow applicability (research physicians only) but trivial to add alongside PubMed. V=2 because it enriches a small provider subset. Build with A1 batch. |

**P1 build output:** 9 source adapters (several are combined). Produces the core identity, exclusion, and participation layer. Sufficient for a functional MVP report.

---

## 3. Priority Tier 2 — Build Second (Post-FOIA Confirmation)

**Gate:** Phase 0 legal gate closed + counsel confirms FOIA/public records data is reportable in consumer reports (both Path A and Path B).
**Target phase:** Phase 2 expansion (high-volume state boards), Phase 2-E (identity resolution), Phase 3-A/B (state board rollout), Phase 3-C (court records), Phase 3-E (review platforms).

These sources require individual counsel confirmation but are expected to be permissible. They represent the differentiation layer of the platform: state board license and discipline data, federal court records, and review signals.

### 3.1 Federal — Moderate Clearance Required

| ID | Source | V | E | L | Priority | Notes |
|----|--------|---|---|---|----------|-------|
| C2 | CourtListener / RECAP Archive | 4 | 2 | L1 | **P2 — #1** | Free Law Project CC0/open license. Large subset of federal court dockets. Use as PACER cost-reduction proxy. Counsel: confirm open-license provenance is sufficient for FCRA accuracy (§ 1681e(b)). Build before paying PACER per-page fees. |
| C1 | PACER (federal courts) | 4 | 3 | L1 | **P2 — #2** | Source of truth for federal court records. Fee-based ($0.10/page, waived under $30/quarter). Build after CourtListener to minimize cost. PACER API (CM/ECF) is available. High value: federal disciplinary actions, malpractice judgments, bankruptcy filings. |
| F5 | DEA Registration | 3 | 4 | L1 | **P2 — #3** | DEA registration is a required credential for prescribers. No public API — counsel must confirm FOIA path or alternative. E=4 because automation requires either FOIA process or assessed scraping risk. Build only after counsel clears a viable integration path. |
| F6 | NPDB Public Use File | 2 | 1 | L1 | **P2 — #4** | Aggregate data only — no individual provider identifiers. Provides state/specialty-level malpractice signal that can enrich report context (e.g., "X% of surgeons in this state had a payment in this period"). Not useful for individual provider scoring. Counsel: confirm aggregate signals are permissible in reports. Low V because no individual data. |

### 3.2 State Medical Boards — FOIA Path

State boards are grouped by provider population (proxy for report request volume). Build adapters in volume order to maximize coverage impact per adapter built.

**FOIA path applies to all boards (S1-S51).** Individual FOIA requests are not scripted here — the FOIA pipeline architecture (request, receive, parse, load) is a single shared framework. The sequencing below determines which states to FOIA first after the framework is built.

**Single framework, per-state FOIA request:** The FOIA adapter framework (one shared pipeline) should be built once in Phase 3-A. Individual state adapters are then the FOIA filing + parser per state.

| # | State | Approx. Licensed MDs | Priority | Notes |
|---|-------|---------------------|----------|-------|
| S5 | California | ~120,000 | P2 — State #1 | Largest physician population. T2-T3 (scraping restriction) — FOIA is the required path. CCPA implications for CA provider data storage. Counsel priority before adapter build. |
| S44 | Texas | ~70,000 | P2 — State #2 | Second-largest. TMB provides data downloads under public information law. T2-T3. Confirm TMB download terms with counsel. |
| S33 | New York | ~68,000 | P2 — State #3 | Third-largest. NY FOIL (FOIA equivalent) is the required path. NY sealing statutes (CPL § 160.50/55) affect court records; confirm state board data independence. T2-T3. |
| S10 | Florida | ~55,000 | P2 — State #4 | High volume. FL Sunshine Law makes FOIA straightforward. MQA Online has a public license search — can supplement FOIA with structured scrape if ToS permits. |
| S39 | Pennsylvania | ~40,000 | P2 — State #5 | High volume. Standard FOIA path. No API known. |
| S14 | Illinois | ~38,000 | P2 — State #6 | High volume. IDFPR covers multiple healthcare professions. No API. FOIA path. |
| S36 | Ohio | ~35,000 | P2 — State #7 | State Medical Board of Ohio publishes disciplinary actions. FOIA + scrape path. |
| S22 | Massachusetts | ~34,000 | P2 — State #8 | One of the more detailed state board systems (online physician profiles). FOIA + scrape. High data quality once obtained. |
| S21 | Maryland | ~28,000 | P2 — State #9 | Standard FOIA path. Disciplinary actions publicly posted. |
| S31 | New Jersey | ~27,000 | P2 — State #10 | Standard FOIA path. Online license verification available. |
| S34 | North Carolina | ~26,000 | P2 — State #11 | License search and disciplinary history public. FOIA path. |
| S23 | Michigan | ~25,000 | P2 — State #12 | LARA license lookup. FOIA path. |
| S48 | Washington | ~23,000 | P2 — State #13 | Washington Medical Commission publishes disciplinary orders. FOIA + scrape. |
| S11 | Georgia | ~22,000 | P2 — State #14 | Standard FOIA path. Disciplinary orders public. |
| S47 | Virginia | ~22,000 | P2 — State #15 | DHP license lookup. Disciplinary actions public. FOIA path. |
| S3 | Arizona | ~20,000 | P2 — State #16 | History of disciplinary orders publicly posted. FOIA path. |
| S38 | Oregon | ~18,000 | P2 — State #17 | License lookup and disciplinary actions public. FOIA path. |
| S43 | Tennessee | ~17,000 | P2 — State #18 | Standard FOIA path. |
| S19 | Louisiana | ~16,000 | P2 — State #19 | License lookup and disciplinary history online. FOIA path. |
| S6 | Colorado | ~16,000 | P2 — State #20 | Disciplinary actions posted publicly. FOIA path. |
| S26 | Missouri | ~16,000 | P2 — State #21 | Standard FOIA path. |
| S24 | Minnesota | ~16,000 | P2 — State #22 | License lookup and disciplinary actions public. FOIA path. |
| S29 | Nevada | ~11,000 | P2 — State #23 | License lookup and disciplinary actions posted. FOIA path. |
| S7 | Connecticut | ~10,500 | P2 — State #24 | Standard FOIA path. |
| S50 | Wisconsin | ~10,500 | P2 — State #25 | DSPS license lookup. FOIA path. |
| S4 | Arkansas | ~7,000 | P2 — State #26 | Disciplinary actions publicly posted. FOIA path. |
| S15 | Indiana | ~15,000 | P2 — State #27 | PLA manages medical licenses. FOIA path. |
| S45 | Utah | ~8,000 | P2 — State #28 | DOPL license lookup. FOIA path. |
| S43–S51 (remaining 23 states + DC) | — | < 8,000 each | P2 — States #29-51 | Standard FOIA path. Build in order of physician population after top 28. See ToS matrix S1-S51 for full list. |

**State board adapter note:** After the top 15 high-volume states are covered, the FOIA framework handles the remaining 36 states with minimal additional adapter work. The framework is the investment; per-state marginal cost is low.

### 3.3 Review Platforms

| ID | Source | V | E | L | Priority | Notes |
|----|--------|---|---|---|----------|-------|
| R1 | Google Places API | 3 | 2 | L1 | **P2 — Reviews #1** | Commercial use permitted via Maps Platform ToS. Key restriction: 30-day cache limit and attribution requirement. Counsel must confirm report inclusion does not constitute "creating an independent dataset." API key required (billing). Build after state board coverage is established — review signals add polish, not core credentialing value. |
| R2 | Yelp Fusion API | 2 | 2 | L1 | **P2 — Reviews #2** | 24-hour cache restriction creates tension with async report generation architecture. Lower V than Google (Google Places is more complete for medical providers). Build only if counsel confirms 24-hour cache is workable and only after R1 is stable. Consider deprioritizing if engineering cost is not justified by marginal signal gain. |

---

## 4. Priority Tier 3 — Contract/Legal Gate Required

**Gate:** Source-specific additional clearance (license negotiation, T4 enterprise contract, or architectural removal decision).
**Target phase:** Phase 3-D (commercial directories), Phase 3-F (insurance networks), Phase 3-G (Doximity decision), post-MVP.

These sources cannot be scheduled for adapter build until the specific legal clearance noted below is obtained. Engineering may pre-read API docs and plan adapter architecture, but no code should be written.

### 4.1 High-Value T3 — Contract Path Likely

| ID | Source | V | E | L | Priority | Clearance Required |
|----|--------|---|---|---|----------|--------------------|
| S52 | FSMB DocInfo | 5 | 2 | L2 | **P3 — Strategic** | If a FSMB license is obtainable with a CRA use clause, it could replace all 51 individual state board FOIA adapters with a single API call. This is the highest-leverage P3 source. Counsel should evaluate FSMB contract terms concurrently with Phase 0 legal gate work. If FSMB signs: deprioritize individual state board adapters above P2 — State #5. |
| S53 | ABMS Board Certification | 4 | 2 | L2 | **P3 — High** | Board certification is a high-trust credential signal. $15/lookup via public tool. Enterprise API requires license. Must negotiate CRA use clause if Path A. Explore concurrently with FSMB. |
| D1 | Ribbon Health | 4 | 3 | L2 | **P3 — High** | Primary commercial provider directory. Ribbon can fill gaps in NPPES taxonomy with richer specialty, affiliation, and network participation data. Contract must explicitly include CRA use authorization if Path A. Negotiate contract during Phase 0 alongside legal gate work. |
| I3 | Licensed Insurance Network Directories (Aetna, BCBS, Cigna, UHC) | 4 | 5 | L2 | **P3 — Deferred** | Very high value for network participation signals but requires carrier-by-carrier contracts. E=5 (multi-carrier, custom integration per carrier). Engineering recommendation: use Ribbon Health (D1) as network proxy for MVP; defer direct carrier contracts to Phase 3-F or post-launch. |

### 4.2 T4 — Architectural Decision Required Before Any Scoping

| ID | Source | V | E | L | Priority | Clearance Required |
|----|--------|---|---|---|----------|--------------------|
| D2 | Healthgrades | 3 | 4 | L3 | **P3 — T4 Decision** | High consumer brand recognition. ToS explicitly prohibits scraping and commercial re-use. Enforcement history against data aggregators. Counsel: confirm whether a licensed data agreement is available and whether CRA use is negotiable. If no commercially viable license path exists, remove from architecture before Phase 3-D scoping. |
| D3 | Vitals (WebMD / Internet Brands) | 2 | 4 | L3 | **P3 — T4 Decision** | Lower brand recognition than Healthgrades. Same prohibition profile. Lower V means the case for contract negotiation is weaker. Engineering recommendation: if Healthgrades (D2) is obtainable, Vitals is likely redundant. Only pursue if D2 falls through. |
| D4 / A3 | Doximity | 3 | 3 | L3 | **P3 — T4 Decision** | Physician professional profiles, peer ratings, publication history. Valuable but ToS explicitly prohibits scraping and commercial data harvesting. No public provider data API. Counsel: assess partner API availability. If no license path exists, remove from architecture before Phase 3-G scoping. |

### 4.3 Court Records — State Level (T2-T3)

State court systems require significant per-state legal and engineering investment. Build only after federal court coverage (C1-C2) is stable and counsel confirms state-by-state reportability.

| ID | Source | V | E | L | Priority | Notes |
|----|--------|---|---|---|----------|-------|
| C3 | California Courts | 4 | 5 | L2 | **P3 — Court #1** | High value (CA provider population). No unified API. CA expungement rules must be respected. CCPA may also apply. Counsel priority. |
| C4 | New York Courts | 4 | 5 | L2 | **P3 — Court #2** | High value. NY sealing statutes (CPL § 160.50/55) are complex. Counsel must confirm which records are reportable in NY. |
| C5 | Texas Courts | 3 | 4 | L1-L2 | **P3 — Court #3** | Tyler Technologies Odyssey API available in some counties. TX expunction law applies. |
| C6 | Florida Courts | 3 | 5 | L1-L2 | **P3 — Court #4** | County-operated, no statewide unified system. FL Sunshine Law is favorable but coverage is inconsistent. |
| C7 | Illinois Courts | 3 | 4 | L1-L2 | **P3 — Court #5** | Cook County has partial online access. No statewide API. |
| C8 | Remaining 45 States — Courts | 2-3 | 5 | L1-L2 | **P3 — Deferred** | Highly variable access model. Engineering recommendation: deprioritize until federal court coverage and top-5 state courts are stable. Evaluate on a state-by-state basis post-Phase 3-C. |

---

## 5. Supplemental Aggregator Sources — Separate Track

These two sources (FSMB and Ribbon) are tracked separately because they are potential multipliers that could change the Phase 2/3 build plan significantly.

| ID | Source | Current Tier | Strategic Option |
|----|--------|-------------|-----------------|
| S52 | FSMB DocInfo | P3 | If licensed: replaces all 51 state board FOIA adapters. Collapses Phase 3-A + 3-B into a single API call. **Pursue contract negotiation during Phase 0 — before legal gate closes.** |
| D1 | Ribbon Health | P3 | If licensed: accelerates Phase 2-D normalization and Phase 3-D. Can serve as insurance network proxy, reducing I3 contract pressure. **Pursue contract negotiation during Phase 0.** |

> **Engineering note:** If FSMB DocInfo is licensed with CRA use authorization, the P2 state board build sequence (#1-51) should be paused and replaced with the FSMB adapter. Do not invest in 51 state board FOIA pipelines until FSMB contract status is confirmed.

---

## 6. Phase 2 Recommended Adapter Build Sequence

This is the canonical sequence for Phase 2 once the legal gate closes. It assumes P1 sources are built as a batch in Phase 2-B, and the FOIA framework is built in Phase 3-A.

### Phase 2-B — Federal Source Adapters (P1 batch)

| Build Order | Source | Adapter Type |
|-------------|--------|-------------|
| 2-B.1 | NPPES / NPI Registry (F1) | Bulk-DL monthly + API lookup |
| 2-B.2 | OIG LEIE (F2) | Bulk-DL monthly + API spot-check |
| 2-B.3 | SAM.gov Exclusions (F3) | API-key bulk + daily delta sync |
| 2-B.4 | CMS Care Compare (F4) | Bulk-DL monthly + API enrichment |
| 2-B.5 | CMS Medicare Enrollment (I1) | Bulk-DL monthly |
| 2-B.6 | CMS Medicaid Enrollment (I2) | Bulk-DL monthly |
| 2-B.7 | NPPES Specialty Crosswalk (I4) | Derived from F1 — no separate adapter |
| 2-B.8 | PubMed / Entrez API (A1) | API lookup on-demand per provider |
| 2-B.9 | ClinicalTrials.gov (A2) | API lookup on-demand per provider |

### Phase 2 Expansion — Post-P1 Stable

| Build Order | Source | Adapter Type | Gate |
|-------------|--------|-------------|------|
| Exp.1 | CourtListener / RECAP (C2) | REST API bulk + per-NPI query | Counsel confirms provenance |
| Exp.2 | PACER (C1) | CM/ECF API, fee-controlled | Counsel confirms re-reporting |
| Exp.3 | Google Places (R1) | Places API per-provider | Counsel confirms report inclusion |
| Exp.4 | Yelp Fusion (R2) | Fusion API per-provider | Counsel confirms 24hr cache path |
| Exp.5 | NPDB Public File (F6) | Bulk-DL + aggregate enrichment | Counsel confirms aggregate use |
| Exp.6 | DEA Registration (F5) | FOIA or counsel-approved path | Counsel confirms integration method |

### Phase 3-A — State Board FOIA Framework + Top States

| Build Order | Source | Adapter Type | Gate |
|-------------|--------|-------------|------|
| 3A.1 | FOIA framework (shared) | Request, receive, parse, load pipeline | Counsel confirms FOIA path |
| 3A.2 | California (S5) | FOIA + CCPA adapter | CA CCPA storage confirmed |
| 3A.3 | Texas (S44) | FOIA + TMB data download | TMB download terms confirmed |
| 3A.4 | New York (S33) | FOIL path + NY sealing filter | NY FOIL counsel confirmation |
| 3A.5 | Florida (S10) | FOIA + MQA scrape | Scrape terms confirmed |

### Phase 3-B — State Board Rollout (States #5-#28+)

Continue down the volume-ordered state board list (see Section 3.2) using the shared FOIA framework. Each state is a FOIA filing + parser, not a new framework. Target 2-3 states per sprint.

> **Note:** If FSMB DocInfo (S52) license is obtained, halt Phase 3-A/3-B and replace with single FSMB API adapter. Resume state board FOIA work only for states where FSMB data is incomplete or requires supplementation.

---

## 7. Deferred / Low-Priority Sources

Sources not included in P1 or P2 sequencing above, either due to low value, pending T4 decisions, or architectural duplication:

| ID | Source | Disposition |
|----|--------|-------------|
| D2 | Healthgrades | Deferred — T4 architectural decision required |
| D3 | Vitals | Deferred — T4; lower value than D2; likely to be removed |
| D4 / A3 | Doximity | Deferred — T4 architectural decision required |
| I3 | Commercial Insurer Networks | Deferred — use Ribbon Health (D1) as proxy for MVP |
| C3 | California Courts | Deferred Phase 3 — high effort, legal complexity |
| C4 | New York Courts | Deferred Phase 3 — sealing statute complexity |
| C5-C8 | Other State Courts | Deferred — evaluate post-Phase 3-C launch |

---

## 8. Source Count by Priority Tier

| Tier | Sources | Description |
|------|---------|-------------|
| P1 | 9 | Federal T1 open-data sources (F1-F4, I1, I2, I4, A1, A2) |
| P2 | 57 | 51 state boards (S1-S51) + FOIA federal (C1-C2, F5-F6) + review platforms (R1, R2) + CourtListener |
| P3 | 14 | Commercial (D1-D4), aggregators (S52-S53), courts (C3-C8), insurer networks (I3) |
| **Total** | **80** | All sources from ToS matrix |

---

## 9. Key Sequencing Dependencies

1. **Legal gate must close before any adapter build begins.** This document drives sequence, not authorization.

2. **FSMB contract determination should happen during Phase 0** — before Phase 3-A planning begins. If obtainable, it collapses 51 FOIA pipelines into one API.

3. **Ribbon Health contract should be pursued during Phase 0.** Affects normalization architecture (C10 in architecture-lock) and insurance network proxy strategy.

4. **NPDB eligible entity determination** affects whether individual NPDB queries are possible (requires counsel + HRSA approval). Do not architect individual NPDB lookups until eligibility is confirmed.

5. **T4 source decisions (Healthgrades, Vitals, Doximity) must be made before Phase 3-D and 3-G are scoped.** If no license path is confirmed, remove these from the component roster to avoid dead architecture surface area.

6. **State court adapters are not MVP-critical.** Federal court coverage (CourtListener + PACER) provides most high-signal records for physicians. State courts add breadth but can be deferred without affecting MVP viability.

---

*This document will be updated in Phase 3-A once the FSMB and Ribbon Health contract determinations are known. If FSMB is licensed, Phase 3-A state board sequence will be replaced with a FSMB adapter phase.*
