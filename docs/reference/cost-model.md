# Data Licensing & Unit Economics Cost Model — Medical Professionals Review

**Document Type:** Business Planning Reference
**Status:** DRAFT — Phase 0-E
**Prepared:** 2026-05-24
**Phase:** 0-E
**Depends on:** `docs/reference/source-priority.md` (Phase 0-D), `docs/reference/tos-matrix.md` (Phase 0-C), `docs/reference/architecture-lock.md`

> **Accuracy Disclaimer:** All costs in this document are estimates derived from public pricing pages, comparable-service benchmarks, and industry knowledge as of 2026. Sources with T3/T4 status have not provided quotes — their costs are estimated ranges and must be validated through contract negotiation. AWS costs are estimated from published on-demand and Reserved Instance pricing. This document is not a financial projection and does not constitute business advice. Update all estimates as actual quotes are received.

---

## 1. Purpose

This document answers three questions for the business and legal teams before the Phase 0 legal gate closes:

1. **What does it cost per report** to generate a report at various volume tiers?
2. **What does the CRA path add** to the cost structure compared to the non-CRA path?
3. **At what price and volume does this business break even** and reach sustainable margins?

The outputs drive: (a) pricing decisions for the consumer product, (b) contract negotiation priority and walk-away thresholds for T3/T4 data sources, and (c) runway planning for the pre-revenue Phase 0-1-2 build period.

---

## 2. Cost Component Categories

| Category | Type | Applicability |
|----------|------|---------------|
| AWS infrastructure (EKS, Aurora, Redis, OpenSearch, S3, CDN) | Fixed monthly | Both paths |
| Third-party licensed data sources (FSMB, ABMS, Ribbon) | Fixed monthly subscription OR per-query variable | Both paths (if contracted) |
| Per-query variable data costs (PACER, Google Places, Yelp) | Variable per report | Both paths |
| FCRA compliance counsel retainer | Fixed monthly | Path A (CRA) delta is higher |
| Cyber / E&O insurance | Fixed monthly | Both paths; Path A carries higher premium |
| Audit ledger (QLDB) | Fixed monthly + variable I/O | Path A only (Path B uses cheaper append-only log) |
| Dispute handling operations | Variable per report (weighted) | Path A only |
| Consumer notification infrastructure | Variable per report | Path A only (adverse action notices) |
| SOC 2 Type II audit | Annual fixed, amortized monthly | Both paths; Phase 6 |
| NPDB eligible entity registration | One-time | Path A only if NPDB individual queries are authorized |

**Out of scope for this document:** Engineer salaries, customer acquisition costs, product management, and non-technical operational headcount. Those belong in a separate financial model once headcount is planned.

---

## 3. AWS Infrastructure Cost by Volume Tier

All figures are monthly estimates in USD. "Reserved" = 1-year reserved instance pricing where applicable.

### 3.1 Volume Tier Definitions

| Tier | Reports/Month | Stage |
|------|---------------|-------|
| T0 — Seed | 1-100 | Beta / private launch |
| T1 — Early | 101-500 | Public soft launch |
| T2 — Growth | 501-2,000 | First-year traction |
| T3 — Scale | 2,001-10,000 | Year 2 growth |
| T4 — Enterprise | 10,001-50,000 | Mature product |

### 3.2 AWS Component Cost Estimates by Tier

| Component | T0 Seed | T1 Early | T2 Growth | T3 Scale | T4 Enterprise |
|-----------|---------|----------|-----------|----------|---------------|
| EKS control plane | $72 | $72 | $72 | $72 | $72 |
| Worker nodes (compute) | $210 | $140 (reserved) | $280 (reserved) | $750 (reserved) | $1,500 (reserved) |
| Aurora PostgreSQL | $50 | $120 (reserved) | $220 (reserved) | $650 (reserved) | $1,300 (reserved) |
| ElastiCache Redis | $50 | $80 (reserved) | $130 (reserved) | $280 (reserved) | $520 (reserved) |
| OpenSearch | $80 | $160 (reserved) | $320 (reserved) | $600 (reserved) | $1,200 (reserved) |
| S3 (storage + requests) | $5 | $12 | $46 | $230 | $1,150 |
| CloudWatch / logging | $25 | $35 | $60 | $120 | $300 |
| NAT Gateway | $45 | $50 | $65 | $90 | $150 |
| ALB / networking | $20 | $25 | $30 | $50 | $100 |
| Data transfer (egress) | $15 | $25 | $50 | $150 | $500 |
| Misc (ECR, Secrets Manager, etc.) | $20 | $25 | $30 | $50 | $100 |
| **AWS Infrastructure Total** | **~$592** | **~$744** | **~$1,303** | **~$3,042** | **~$6,892** |

> **Notes:**
> - T0 uses on-demand pricing. T1+ assumes 1-year reserved purchases after the first stable month of operation.
> - Worker node counts: T0=3x m5.large, T1=3x m5.large reserved, T2=6x m5.large reserved, T3=10x m5.xlarge reserved, T4=20x m5.xlarge reserved.
> - Aurora: T0=db.t3.medium (dev), T1/T2=db.r6g.large, T3=db.r6g.2xlarge Multi-AZ, T4=db.r6g.4xlarge Multi-AZ.
> - OpenSearch: T0/T1=2x t3.medium.search, T2=4x m6g.large.search, T3=6x r6g.large.search, T4=12x r6g.large.search.
> - S3 storage assumes: T0=100GB, T1=500GB, T2=2TB, T3=10TB, T4=50TB (raw source data + reports accumulated).
> - These estimates cover infrastructure only. Temporal (workflow orchestration) runs on EKS and is included in worker node cost.

### 3.3 QLDB Audit Ledger (Path A only — additional)

| Tier | QLDB Storage | QLDB I/O (100 events/report) | Total QLDB Add |
|------|-------------|------------------------------|----------------|
| T0 | $5 | <$0.01 | ~$5 |
| T1 | $15 | ~$0.01 | ~$15 |
| T2 | $40 | ~$0.06 | ~$40 |
| T3 | $150 | ~$0.30 | ~$150 |
| T4 | $600 | ~$1.45 | ~$600 |

> **QLDB sunset note:** AWS has announced intentions to deprecate QLDB as a standalone service. The architecture-lock accepts QLDB as a calculated compliance trade-off (DECISIONS.md Entry 001). Engineering must monitor the AWS roadmap and may need to migrate to Aurora-based immutable ledger tables before Phase 4-F. Migration cost not modeled here.

---

## 4. Per-Source Data Acquisition Costs

### 4.1 P1 Federal Open-Data Sources (Zero Direct Cost)

All nine P1 sources are CC0 / public domain with no per-query fee. The only costs are:
- Infrastructure to schedule and run bulk download jobs (captured in AWS estimate above)
- Engineer time to build and maintain adapters (one-time build cost, not ongoing COGS)

| Source | Cost Model | Monthly Cost | Per-Report Cost |
|--------|-----------|-------------|-----------------|
| NPPES (F1) | Bulk-DL + API-Free | $0 data | $0 |
| OIG LEIE (F2) | Bulk-DL + API-Free | $0 data | $0 |
| SAM.gov (F3) | API key (free) | $0 data | $0 |
| CMS Care Compare (F4) | Bulk-DL + API-Free | $0 data | $0 |
| CMS Medicare Enrollment (I1) | Bulk-DL | $0 data | $0 |
| CMS Medicaid Enrollment (I2) | Bulk-DL | $0 data | $0 |
| PubMed / NCBI Entrez (A1) | API-Free | $0 data | $0 |
| ClinicalTrials.gov (A2) | API-Free | $0 data | $0 |
| NPPES Crosswalk (I4) | Derived from F1 | $0 data | $0 |

**P1 total data cost: $0/month.** The P1 adapter suite produces a fully functional MVP report using only free data.

### 4.2 P2 Variable Data Costs (Fee-Per-Query)

These sources have per-query fees or free tiers with hard caps.

#### PACER — Federal Court Records (C1)

| Volume Tier | Queries/Month | Quarterly Pages Requested | Quarterly Waiver ($30) | Estimated Cost |
|-------------|--------------|--------------------------|------------------------|----------------|
| T0 (100) | ~15 (15% hit rate) | ~150 pages (10p/case) | Covered | **$0** |
| T1 (500) | ~75 | ~750 pages | Partly covered ($30 waived; $45 excess) | **~$15/mo** |
| T2 (2,000) | ~300 | ~3,000 pages | Mostly billable | **~$90/mo** |
| T3 (10,000) | ~1,500 | ~15,000 pages | Fully billable | **~$450/mo** |
| T4 (50,000) | ~7,500 | ~75,000 pages | Fully billable | **~$2,250/mo** |

> Assumptions: 15% of reports query PACER (providers with non-trivial federal court activity identified via CourtListener pre-screen); average 10 pages/docket. CourtListener (free) is used as a pre-screen to minimize PACER queries.

**Per-report weighted cost:** $0.00-$0.05 depending on tier.

#### Google Places API (R1)

| Volume Tier | Monthly Queries | Free Credit ($200) | Net Cost | Per-Report |
|-------------|----------------|--------------------|-----------|---------:|
| T0 (100) | 100 | Covered | $0 | $0.00 |
| T1 (500) | 500 | Covered | $0 | $0.00 |
| T2 (2,000) | 2,000 | Covered | $0 | $0.00 |
| T3 (10,000) | 10,000 | $170 covered (10K x $0.017); $170/month = 10,000 requests; covered | $0 | $0.00 |
| T4 (50,000) | 50,000 | $200 = 11,765 free; 38,235 paid | ~$650/mo | **$0.013** |

> Place Details API: $17/1,000 requests = $0.017/request. Google's $200/month free credit covers up to ~11,765 Place Details requests. Effectively zero cost below ~12,000 reports/month.

**Per-report weighted cost at scale:** $0.00-$0.013.

#### Yelp Fusion API (R2)

| Volume Tier | Monthly Queries | Free Tier (500/day = ~15,000/mo) | Net Cost |
|-------------|----------------|----------------------------------|---------|
| T0-T2 | < 2,000 | Covered | $0 |
| T3 (10,000) | 10,000 | Covered | $0 |
| T4 (50,000) | 50,000 | 35,000 paid | ~$50-150/mo (estimated) |

> Yelp Fusion paid tier pricing is not public; estimated $50-150/month at enterprise volumes based on comparable API pricing. Negligible at all practical volumes for this build.

**Per-report weighted cost:** ~$0.00-$0.003. Treated as rounding error.

### 4.3 P3 Licensed Data Sources — Contract-Dependent Costs

These costs are **highly uncertain** — no quotes have been received. Ranges are engineering estimates based on comparable services. All require contract negotiation before costs can be confirmed.

#### FSMB DocInfo (S52) — Strategic Source

If licensed, FSMB DocInfo replaces 51 individual state board FOIA adapters with a single API. It is the highest-leverage contract to pursue.

| Cost Model | Estimated Cost | Notes |
|-----------|----------------|-------|
| Per-query (Scenario A) | $2-5/provider query | Common for credentialing APIs |
| Subscription (Scenario B) | $2,000-8,000/month | Flat rate up to a volume ceiling |

**Scenario A impact at scale:**
- T2 (2,000 reports/month): $4,000-$10,000/month — unacceptable unit economics
- T3 (10,000/month): $20,000-$50,000/month — report pricing would need to be $30+ just for FSMB alone

**Scenario B impact (subscription):**
- Subscription breaks even vs. Scenario A at ~400-1,600 reports/month
- Strong preference: negotiate flat subscription with a reasonable volume cap

**FSMB vs. DIY FOIA engineering ROI:**
- DIY FOIA adapter build (51 states, shared framework): estimated 14-18 weeks of engineering
- At $12,000/month average engineer cost: ~$40,000-54,000 one-time engineering cost
- FSMB subscription at $5,000/month: pays back in 8-11 months vs. DIY, then adds ongoing cost
- Decision rule: **If FSMB costs < $3,000/month AND covers all 51 states accurately, license it. If > $5,000/month, build the FOIA framework.**
- Engineering recommendation: Negotiate FSMB during Phase 0. If price > $5,000/month or CRA use is not contractually guaranteed, proceed with DIY FOIA.

#### ABMS Board Certification (S53)

| Cost Model | Estimated Cost | Notes |
|-----------|----------------|-------|
| Retail / individual lookup | $15/query | Published on ABMS website |
| Enterprise contract | $3-8/query (estimated) | No public enterprise pricing |
| Enterprise subscription | Unknown | Not confirmed to exist |

> **Warning:** At $15/report (retail), ABMS completely dominates COGS and makes the product uneconomical at most price points. At $5/report (enterprise estimate), ABMS costs $10,000/month at T3 scale.
>
> **Recommendation:** Include ABMS verification only in a premium tier report (e.g., $75+ price point). Do not include in base reports until enterprise subscription pricing is confirmed. Alternatively, use NPPES taxonomy + NPI lookup as a board-certification proxy where available.

| Inclusion Strategy | Per-Report ABMS Cost | Break-Even Volume at $35 price |
|-------------------|---------------------|-------------------------------|
| All reports (retail $15) | $15.00 | This is impossible — ABMS alone exceeds base price |
| All reports (enterprise est. $5) | $5.00 | Only works at $50+ price points |
| Premium tier only (30% of reports) | $1.50 (weighted) | Workable at $35+ base price |
| Excluded from MVP | $0.00 | Simplest; add post-MVP when contract is in hand |

#### Ribbon Health (D1) — Primary Commercial Directory

| Cost Model | Estimated Cost | Notes |
|-----------|----------------|-------|
| Per API call | $0.10-$0.50/enrichment call | Comparable healthcare data APIs |
| Subscription | $3,000-10,000/month | Industry range for provider data access |

**Recommendation:** Negotiate a flat subscription. At $0.25/report (per-call model), T3 scale = $2,500/month. Subscription is better value above ~10,000-40,000 reports/month.

| Subscription Scenario | Monthly Cost | Break-Even Vs. Per-Call |
|----------------------|-------------|------------------------|
| Low ($3,000/month) | $3,000 | 12,000 reports/month |
| Mid ($6,000/month) | $6,000 | 24,000 reports/month |
| High ($10,000/month) | $10,000 | 40,000 reports/month |

> **At T2-T3 scale, per-call Ribbon pricing is likely cheaper than a subscription.** Only switch to subscription at T4.

#### T4 Sources — Cost Highly Speculative

| Source | Estimated Cost | Confidence | Recommendation |
|--------|---------------|------------|----------------|
| Healthgrades (D2) | Unknown — enterprise contract required | Very low | Defer until T3 scale; demand CRA use clause in any contract |
| Vitals / WebMD (D3) | Unknown | Very low | Deprioritize; only pursue if Healthgrades unavailable |
| Doximity (D4) | Unknown — partner API may not exist | Very low | Get T4 architectural decision before Phase 3-G; if no partner path, remove |
| Commercial insurer networks (I3) each carrier | $1,000-5,000/month per carrier (estimated) | Very low | Use Ribbon Health as proxy; defer carrier-by-carrier until T3+ |

---

## 5. CRA Path vs. Non-CRA Path — Cost Delta

This section quantifies the additional fixed and variable costs of Path A (CRA) vs. Path B (non-CRA).

### 5.1 Fixed Monthly Cost Delta (Path A over Path B)

| Cost Item | Path B (Non-CRA) | Path A (CRA) | Monthly Delta |
|-----------|-----------------|--------------|--------------|
| FCRA compliance counsel (specialized) | $1,000-2,000 general counsel | $3,000-8,000 specialized FCRA counsel | **+$2,000-6,000** |
| Cyber / E&O insurance | $500-1,500/month | $2,000-5,000/month (higher coverage required) | **+$1,500-3,500** |
| QLDB audit ledger (see Section 3.3) | $0 (simpler log) | $15-600/month by tier | **+$15-600** |
| Dispute handling staff (0.5 FTE part-time) | $0 | $1,000-3,000/month | **+$1,000-3,000** |
| NPDB eligible entity registration (one-time / amortized) | $0 | $2,000-5,000 one-time = ~$170-420/month over 12 months | **+$170-420** |
| SOC 2 audit premium (broader scope on CRA path) | $2,000-3,000/month (amortized) | $2,500-4,000/month | **+$500-1,000** |
| **Total Path A Fixed Add** | — | — | **+$5,185-14,520/month** |
| **Midpoint estimate** | — | — | **+$9,800/month** |

### 5.2 Variable Per-Report Cost Delta (Path A over Path B)

| Cost Item | Path B | Path A | Per-Report Delta |
|-----------|--------|--------|-----------------|
| Adverse action notice (§ 1681m, via SES email) | $0 | ~$0.02/report (SES + template render) | **+$0.02** |
| Consumer disclosure on request (§ 1681g) — ~1-2% of reports trigger | $0 | ~$0.10/request x 1.5% = $0.0015/report | **+$0.002** |
| Dispute resolution labor (1% dispute rate x 30min x $50/hr) | $0 | ~$0.25/report weighted | **+$0.25** |
| FCRA-compliant report format (extra content, audit writes) | $0 | ~$0.01/report | **+$0.01** |
| **Total Path A Variable Add** | — | — | **+$0.26-0.30/report** |

### 5.3 Summary — Path A vs. Path B

| Scenario | Path B Total Fixed | Path A Total Fixed | Path A Variable Add |
|----------|-------------------|-------------------|---------------------|
| Low estimate (T1 Early) | ~$744 infra | +$5,185 = ~$5,929 | +$0.26/report |
| Mid estimate (T2 Growth) | ~$1,303 infra | +$9,800 = ~$11,103 | +$0.26/report |
| High estimate (T3 Scale) | ~$3,042 infra | +$14,520 = ~$17,562 | +$0.28/report |

> **Implication:** The CRA path effectively adds ~$10,000/month in fixed overhead at steady state, independent of volume. This overhead is more damaging at low volume tiers (T0-T1) where it can represent 5-10x the infrastructure cost. At T3+ scale, it becomes a smaller percentage of total costs.

---

## 6. Unit Economics Model

### 6.1 Total Fixed Cost by Scenario

Three scenarios modeled — differentiated by which licensed data sources have been contracted:

| Scenario | Description | Fixed Monthly Costs |
|----------|-------------|---------------------|
| **Baseline (P1 only)** | Only free federal sources in reports. No FSMB, ABMS, or Ribbon. | AWS infra only |
| **Licensed (FSMB + Ribbon)** | FSMB DocInfo + Ribbon Health subscriptions active | AWS + $5,000 (FSMB mid) + $4,000 (Ribbon per-call avg at growth) |
| **Licensed + CRA** | FSMB + Ribbon + Path A CRA overhead | AWS + $9,000 data + $9,800 CRA |

### 6.2 Per-Report Variable Cost Summary

| Source Category | Per-Report Variable Cost | Notes |
|-----------------|--------------------------|-------|
| AWS compute (Temporal workflow + PDF) | $0.03-0.08 | 8-15 workflow activities + PDF generation |
| AWS storage (S3 per report) | $0.005-0.010 | ~500KB-2MB stored per report |
| PACER (weighted, 15% hit rate) | $0.00-0.05 | $0 under free waiver at T0-T1; escalates at T2+ |
| Google Places API | $0.00-0.013 | $0 under free credit at T0-T3; negligible at T4 |
| Yelp Fusion | $0.00-0.003 | Free tier covers all practical volumes |
| **Total variable (Baseline, no licensed data)** | **$0.035-0.166** | — |
| FSMB (if subscription — excluded from variable) | $0 (in fixed) | — |
| Ribbon (if per-call at $0.25) | $0.25 | Applicable at T0-T3 before subscription threshold |
| ABMS (if per-query at $5, premium only) | $0 (excluded from base) or $5 | Only in premium SKU |
| Path A CRA variable adds | +$0.26-0.30 | Dispute, notice, disclosure |

**All-in variable cost per report:**
- Baseline (no licensed data, Path B): **$0.04-$0.17**
- Licensed + per-call Ribbon (Path B): **$0.29-$0.42**
- Licensed + per-call Ribbon + Path A: **$0.55-$0.72**

### 6.3 Unit Economics Tables by Price Point

#### Scenario A — Baseline Only (P1 Free Sources, Path B Non-CRA)

*Variable cost per report: $0.10 (midpoint). Fixed = AWS infra by tier.*

| Tier | Reports/Mo | Price | Revenue | Variable COGS | Fixed Costs | Gross Profit | Gross Margin |
|------|-----------|-------|---------|--------------|-------------|-------------|-------------|
| T0 | 100 | $35 | $3,500 | $10 | $592 | $2,898 | 83% |
| T1 | 500 | $35 | $17,500 | $50 | $744 | $16,706 | 95% |
| T2 | 2,000 | $35 | $70,000 | $200 | $1,303 | $68,497 | 98% |
| T3 | 10,000 | $35 | $350,000 | $1,000 | $3,042 | $345,958 | 99% |
| T0 | 100 | $25 | $2,500 | $10 | $592 | $1,898 | 76% |
| T1 | 500 | $25 | $12,500 | $50 | $744 | $11,706 | 94% |
| T2 | 2,000 | $25 | $50,000 | $200 | $1,303 | $48,497 | 97% |

> Baseline scenario: excellent margins — but the product has limited differentiation (federal data only, no state board license status, no court records). This is a minimal viable product, not a competitive one.

#### Scenario B — Licensed Data Sources (FSMB + Ribbon, Path B Non-CRA)

*Variable cost: $0.36/report (adds $0.25 Ribbon per-call). Fixed adds: $5,000 FSMB + variable Ribbon (below subscription threshold, so per-call is included in variable above). Assume FSMB subscription $5,000/month.*

| Tier | Reports/Mo | Price | Revenue | Variable COGS | Fixed Costs | Gross Profit | Gross Margin |
|------|-----------|-------|---------|--------------|-------------|-------------|-------------|
| T0 | 100 | $35 | $3,500 | $36 | $5,592 | -$2,128 | Negative |
| T1 | 500 | $35 | $17,500 | $180 | $5,744 | $11,576 | 66% |
| T2 | 2,000 | $35 | $70,000 | $720 | $6,303 | $62,977 | 90% |
| T3 | 10,000 | $35 | $350,000 | $3,600 | $8,042 | $338,358 | 97% |
| T0 | 100 | $50 | $5,000 | $36 | $5,592 | -$628 | Negative |
| T1 | 500 | $50 | $25,000 | $180 | $5,744 | $19,076 | 76% |
| T2 | 2,000 | $50 | $100,000 | $720 | $6,303 | $92,977 | 93% |

#### Scenario C — Licensed Data + Path A (CRA) — Full Build

*Adds $9,800/month fixed (CRA overhead) + $0.28/report variable (CRA ops). Total variable: $0.64/report. Total fixed adds: $9,800 CRA + $5,000 FSMB = $14,800 on top of AWS.*

| Tier | Reports/Mo | Price | Revenue | Variable COGS | Fixed Costs | Gross Profit | Gross Margin |
|------|-----------|-------|---------|--------------|-------------|-------------|-------------|
| T0 | 100 | $35 | $3,500 | $64 | $15,392 | -$11,956 | Negative |
| T1 | 500 | $35 | $17,500 | $320 | $15,544 | $1,636 | 9% |
| T2 | 2,000 | $35 | $70,000 | $1,280 | $16,103 | $52,617 | 75% |
| T3 | 10,000 | $35 | $350,000 | $6,400 | $17,842 | $325,758 | 93% |
| T1 | 500 | $50 | $25,000 | $320 | $15,544 | $9,136 | 37% |
| T2 | 2,000 | $50 | $100,000 | $1,280 | $16,103 | $82,617 | 83% |
| T2 | 2,000 | $75 | $150,000 | $1,280 | $16,103 | $132,617 | 88% |

---

## 7. Break-Even Analysis

Break-even volume (reports/month) = Fixed Costs / (Price - Variable Cost/Report)

### 7.1 Break-Even Table

| Scenario | Price | Variable Cost | Contribution Margin | Fixed Costs | Break-Even Volume |
|----------|-------|---------------|--------------------|--------------|-----------------:|
| Baseline (Path B) | $35 | $0.10 | $34.90 | $744 (T1) | **22 reports/mo** |
| Baseline (Path B) | $25 | $0.10 | $24.90 | $744 (T1) | **30 reports/mo** |
| Licensed + Path B | $35 | $0.36 | $34.64 | $5,744 | **166 reports/mo** |
| Licensed + Path B | $25 | $0.36 | $24.64 | $5,744 | **233 reports/mo** |
| Licensed + Path A | $35 | $0.64 | $34.36 | $15,544 | **452 reports/mo** |
| Licensed + Path A | $50 | $0.64 | $49.36 | $15,544 | **315 reports/mo** |
| Licensed + Path A | $75 | $0.64 | $74.36 | $15,544 | **209 reports/mo** |
| Licensed + Path A | $35 | $0.64 | $34.36 | $16,103 (T2) | **469 reports/mo** |

> **Key finding:** The business breaks even at very low volumes in the baseline scenario. Licensed data sources are the primary break-even driver. The CRA path is financially viable by T2 growth phase at $35 pricing, and improves significantly at $50-75 price points.

### 7.2 Minimum Revenue to Cover Costs (Monthly)

| Scenario | T0 Fixed | T1 Fixed | T2 Fixed | Revenue needed at T2 for 50% GM |
|----------|----------|----------|----------|--------------------------------|
| Baseline (Path B) | $592 | $744 | $1,303 | $2,806 (81 reports at $35) |
| Licensed (Path B) | $5,592 | $5,744 | $6,303 | $13,126 (375 reports at $35) |
| Licensed (Path A) | $15,392 | $15,544 | $16,103 | $33,486 (957 reports at $35) |

---

## 8. Build Period Cost Estimate (Pre-Revenue)

During Phase 0-1 (legal gate + foundations), the product generates zero revenue. Infrastructure cost before any reports are generated:

| Period | Duration | Monthly Cost | Total Cost |
|--------|----------|-------------|-----------|
| Phase 0 remaining (legal gate) | ~14 weeks | $592 (minimal infra) | ~$3,500 |
| Phase 1 Foundations | 4 months | $592-744 (dev infra) | ~$2,600 |
| Phase 2 Core Identity & MVP | 4 months | $744-1,303 (ramping) | ~$4,100 |
| **Total pre-revenue infra** | **~10 months** | — | **~$10,200** |

> This is infrastructure-only. Add engineer compensation, legal counsel fees (~$15,000-30,000 for FCRA opinion + source ToS review), and licensed data source onboarding costs to get total pre-revenue burn.

**Legal counsel cost estimate for Phase 0:**
- FCRA opinion letter (CRA vs. non-CRA determination): $5,000-20,000 (one-time)
- ToS review of 80 sources (phased, not all at once): $10,000-25,000
- Contract review for FSMB + Ribbon + ABMS: $3,000-8,000
- Total Phase 0 legal: **$18,000-53,000**

---

## 9. Sensitivity Analysis — Key Cost Unknowns

Five unknowns can swing monthly costs by $5,000-20,000+. These should be resolved during Phase 0 contract negotiations.

### 9.1 FSMB Contract Price

| FSMB Price | Impact on Break-Even (T2, $35 price) | Engineering Alternative |
|-----------|--------------------------------------|------------------------|
| $0 (not licensed) | Break-even at 37 reports (DIY FOIA, $1,303 fixed) | Build 51 FOIA adapters (~16 weeks engineering) |
| $2,000/month | Break-even at 95 reports | License it — cheaper than DIY above ~100 reports |
| $5,000/month | Break-even at 185 reports | Marginal — evaluate based on data quality vs. DIY |
| $8,000/month | Break-even at 270 reports | Only license if FSMB data quality is significantly better than DIY FOIA |
| $10,000/month | Break-even at 328 reports | Build DIY FOIA instead |

### 9.2 ABMS Inclusion Strategy

| Strategy | ABMS Per-Report Cost | T2 (2,000 reports) Monthly ABMS Cost | Gross Margin Impact at $35 |
|----------|---------------------|--------------------------------------|--------------------------|
| Not included | $0 | $0 | Baseline |
| Premium SKU only (20% of reports) at $5 enterprise | $1.00 (weighted) | $2,000 | -2.9 percentage points |
| All reports at $5 enterprise | $5.00 | $10,000 | -14.3 percentage points |
| All reports at $15 retail | $15.00 | $30,000 | Revenue would be negative |

> **Decision required before Phase 3-G scoping:** ABMS must be a premium-only add-on OR must have an enterprise subscription contract negotiated. Including ABMS at retail pricing in a $35 report is economically impossible.

### 9.3 Dispute Rate (Path A only)

| Dispute Rate | Labor per Dispute | Monthly Dispute Cost (T2, 2,000 reports) | Per-Report Weighted |
|-------------|------------------|------------------------------------------|---------------------|
| 0.5% | 30 min at $50/hr | $150 | $0.075 |
| 1.0% | 30 min at $50/hr | $300 | $0.150 |
| 2.0% | 30 min at $50/hr | $600 | $0.300 |
| 2.0% | 60 min at $50/hr | $1,200 | $0.600 |

> **Architecture note:** The architecture-lock (R14 mitigation) notes that dispute volume staffing needs a defined ceiling. At 2% dispute rate + 60 min average resolution, T3 scale (10,000 reports/month) generates $6,000/month in dispute labor — manageable. At 5% dispute rate, it becomes a serious operational cost. Investing in data accuracy (C12 precision threshold of >98%) is the primary cost-reduction mechanism for disputes.

### 9.4 Ribbon Health Pricing (Per-Call vs. Subscription)

| Ribbon Cost Model | T2 Monthly Cost | T3 Monthly Cost | Recommendation |
|-------------------|----------------|----------------|---------------|
| $0.10/call | $200 | $1,000 | Per-call preferred at T0-T2 |
| $0.25/call | $500 | $2,500 | Per-call preferred at T0-T1 |
| $0.50/call | $1,000 | $5,000 | Subscription at this price |
| $4,000/month subscription | $4,000 | $4,000 | Subscribe when per-call > $4,000/month |
| $8,000/month subscription | $8,000 | $8,000 | Only subscribe if volume-unlimited |

> Threshold: switch from per-call to subscription when monthly per-call cost > subscription price. At $0.25/call, subscription threshold is 16,000 calls/month (T3-T4 boundary).

### 9.5 Pricing Power Sensitivity

At T2 Growth (2,000 reports/month), Licensed + Path A (CRA) scenario:

| Price Point | Revenue | Total Costs | Gross Profit | Gross Margin |
|-------------|---------|-------------|-------------|-------------|
| $20 | $40,000 | $17,383 | $22,617 | 57% |
| $25 | $50,000 | $17,383 | $32,617 | 65% |
| $35 | $70,000 | $17,383 | $52,617 | 75% |
| $50 | $100,000 | $17,383 | $82,617 | 83% |
| $75 | $150,000 | $17,383 | $132,617 | 88% |

> **Pricing recommendation (to be validated by market research):** $35-50 as the consumer sweet spot for a comprehensive physician report, with a premium $75 tier that includes ABMS certification lookup. The cost structure easily supports $35 pricing at T2+ scale. Sub-$25 pricing would require strong volume (T3+) to sustain Path A overhead.

---

## 10. Contract Negotiation Priorities

Ranked by potential cost impact on unit economics:

| Priority | Source | Why | Target Outcome |
|----------|--------|-----|---------------|
| 1 | **FSMB DocInfo** | Collapses 51 FOIA adapters; impacts Phase 3 timeline | Subscription < $5,000/month with CRA use clause |
| 2 | **ABMS Board Certification** | $15/retail is economically impossible at scale | Enterprise subscription OR per-query < $3; or agree to premium-only SKU |
| 3 | **Ribbon Health** | Primary commercial directory; affects report quality | Per-call $0.10-0.25 for T2-T3; volume-based subscription for T4 |
| 4 | **FCRA / legal counsel** | $9,800/month fixed delta on Path A is the largest single cost driver | Scope-limited retainer; prioritize FCRA opinion, ToS review, source contracts in phases |
| 5 | **Healthgrades / Doximity** | T4 sources; unquantifiable until negotiated | Determine whether licensed path exists; if > $1/report, remove from architecture |

---

## 11. Key Assumptions and Risks

| Assumption | Risk if Wrong |
|-----------|--------------|
| FSMB licensed at $2,000-8,000/month | If no license is available, 51-state FOIA pipeline adds 14-18 weeks engineering and modest ongoing FOIA ops cost |
| ABMS enterprise pricing $3-8/query | If only retail ($15/lookup) is available, ABMS must be excluded from all reports |
| Dispute rate 1% (industry average for background check CRAs) | If medical report disputes run higher due to data complexity, CRA ops costs could 2-3x |
| AWS Reserved Instance pricing captured | On-demand pricing at growth/scale tiers is ~40% higher; plan reserved purchases 30 days before each tier threshold |
| Temporal self-hosted on EKS (no Temporal Cloud fee) | If Temporal Cloud is used: $25/million workflow actions. At T3 (10,000 reports x 20 actions): $5/month — negligible |
| Google Places $200/month free credit persists | Google has adjusted Maps Platform pricing before; model at $0.017/report as fallback |
| Path A FCRA counsel $3,000-8,000/month | Healthcare FCRA specialists are scarce; retainer could be higher in early engagement |
| QLDB remains available on AWS | See Section 3.3 note on QLDB sunset risk |

---

## 12. Recommended Actions Before Phase 0 Legal Gate Closes

1. **Engage FSMB** — Request enterprise API pricing and confirm whether CRA use is permissible. This is the single most important contract for Phase 3 cost and timeline.

2. **Engage ABMS** — Request enterprise subscription pricing. Without a workable price, exclude ABMS from base report SKU.

3. **Engage Ribbon Health** — Request pricing tiers. Establish per-call vs. subscription threshold.

4. **Confirm FCRA counsel retainer scope** — Define a phased engagement (FCRA opinion first, then source ToS review, then contract review) to control cost.

5. **T4 decision on Healthgrades, Vitals, Doximity** — Brief determination call with counsel: are licensed data agreements available in principle? If not, formally remove from architecture before Phase 3-D/3-G scoping begins.

6. **Set internal dispute rate target** — Define the acceptable ceiling (e.g., < 1.5%) and tie it to the C12 identity resolution precision target (>98%). This is both a quality and a cost-control decision.

7. **Set pricing before Phase 2-J (Stripe integration)** — The cost model supports $35-50 as sustainable pricing with the Licensed + Path A scenario at T2 growth. Validate with user research; price anchoring is easier to set up-front than to change post-launch.

---

*This document will be revised as actual contract quotes are received from FSMB, ABMS, and Ribbon Health. Update the "Actual" column in each table as quotes come in during Phase 0 negotiations.*
