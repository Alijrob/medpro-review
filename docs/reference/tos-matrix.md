# ToS Analysis Matrix — Medical Professionals Review

**Document Type:** Engineering Preliminary Assessment — Legal Counsel Review Required
**Status:** DRAFT — Awaiting Legal Sign-Off Per Source
**Prepared:** 2026-05-24
**Phase:** 0-C
**Audience:** Legal counsel + engineering leads

> **Disclaimer:** This matrix is an engineering-level preliminary assessment of publicly available terms of service, data use policies, and integration methods. It does not constitute legal advice and does not authorize integration with any source. Legal counsel must independently review and sign off on each source before integration work begins. All "CRA Use Permitted" assessments are engineering reads of public ToS language — counsel's determination governs.

---

## Risk Tier Legend

| Tier | Label | Meaning |
|------|-------|---------|
| **T1** | Low | Federal open government data or explicit open/CC0 license. No known restriction on aggregation or CRA use. Engineering can scope adapters post-legal-gate with minimal concern pending counsel confirmation. |
| **T2** | Medium | Public data but ToS is silent or ambiguous on bulk aggregation, CRA use, or commercial re-reporting. Likely permissible with appropriate disclosures, but requires legal review before integration begins. |
| **T3** | High | ToS likely restricts aggregation, CRA use, or commercial re-use. Contract negotiation or explicit license required. Legal counsel must evaluate before any integration work is scoped. |
| **T4** | Critical | ToS explicitly prohibits re-aggregation, known enforcement history against data aggregators, or enterprise contract required with specific CRA/non-CRA clauses. Must resolve via legal before source is included in architecture. |

---

## Integration Method Legend

| Code | Method |
|------|--------|
| **API** | Documented public REST/JSON API, key required |
| **API-Free** | Documented public REST/JSON API, no key required |
| **Bulk-DL** | Scheduled bulk file download (CSV/XML/NDJSON) |
| **FOIA** | FOIA or public records request for periodic bulk data |
| **Licensed** | B2B data license agreement, custom delivery |
| **Scrape** | Web scraping (no official API — highest ToS risk) |
| **PACER** | Federal court PACER/ECF system (fee-based) |
| **Manual** | No automation path; individual lookup only |

---

## How to Use This Matrix

- **Engineering:** Use the Integration Method column to scope adapter design. Do not begin adapter work on any T3/T4 source without counsel sign-off.
- **Legal counsel:** Review the "ToS Notes" and "CRA Use Permitted" columns. Update the "Legal Sign-Off" column with your determination and date. Flag any sources where the integration method itself (e.g., scraping) creates independent legal risk regardless of FCRA status.
- **Product:** Use the Risk Tier column to sequence source prioritization in Phase 0-D.

---

## 1. Federal Government Sources

| # | Source | Data Provided | Integration | ToS / Data Policy URL | Risk Tier | CRA Use Permitted | ToS Notes | Legal Sign-Off |
|---|--------|--------------|-------------|----------------------|-----------|-------------------|-----------|----------------|
| F1 | **NPPES / NPI Registry** (CMS) | NPI numbers, provider names, specialties, addresses, taxonomy codes, practice locations | API-Free + Bulk-DL | https://npiregistry.cms.hhs.gov/api-page | **T1** | Likely yes — public federal data | CC0-equivalent; CMS explicitly states data is public domain. Bulk download available at https://download.cms.gov/nppes/NPI_Files.html. No known restriction on aggregation or CRA use. | ☐ Pending |
| F2 | **OIG LEIE** (HHS Office of Inspector General) | Excluded individuals and entities, exclusion type, dates, basis | Bulk-DL + API | https://oig.hhs.gov/exclusions/exclusions_download.asp | **T1** | Likely yes — federal exclusion list | Explicitly public federal data. OIG encourages integration. Monthly bulk CSV download. Limited API also available. No known restriction on CRA use. | ☐ Pending |
| F3 | **SAM.gov — Exclusions** (GSA) | Federal debarments and suspensions, EPLS data | API + Bulk-DL | https://open.gsa.gov/api/sam/ | **T1** | Likely yes — federal open data | GSA open data; requires API key (free). CC0 data license. Primary use case includes employment/contractor screening — supports CRA pathway. | ☐ Pending |
| F4 | **CMS Care Compare / Provider Data** (CMS) | Medicare participation, quality measures, patient satisfaction, hospital affiliations, malpractice | API-Free + Bulk-DL | https://data.cms.gov/provider-data | **T1** | Likely yes — CC0 license | data.cms.gov uses CC0 license explicitly. Covers physicians, group practices, hospitals. Highly valuable for insurance network participation and quality signals. | ☐ Pending |
| F5 | **DEA Registration Lookup** (DEA) | DEA registration number validity, schedule authorization | Manual / Scrape | https://www.deadiversion.usdoj.gov/webforms/verifyCertificate.jsp | **T2** | Unknown — no ToS found for bulk use | No public API. Individual lookup only via web form. Scraping would be required for automation. DEA website terms prohibit automated queries. Counsel should assess whether FOIA path is viable for bulk validation. | ☐ Pending |
| F6 | **NPDB — Public Use Data File** (HRSA) | Aggregate malpractice payment and adverse action counts by state/specialty (no individual identifiers in public file) | Bulk-DL | https://www.npdb.hrsa.gov/resources/publicData.jsp | **T2** | Partial — public file has no individual IDs | The NPDB Public Use File is aggregate only; it does not contain individual provider identifiers. Individual queries require either the provider's self-query or an eligible entity query (hospitals, licensing boards). Engineering cannot query individual records. Counsel: confirm whether aggregate signals from the public file are usable in reports without triggering NPDB access restrictions. | ☐ Pending |

---

## 2. State Medical Licensing Boards

**General Notes for All State Boards:**
- Integration method for most boards is **FOIA (bulk)** for periodic batch + **Scrape** for real-time license status lookup.
- Most state boards have web-based license verification portals with no public API.
- FOIA requests for licensee data are generally permissible as public records, but some states exempt certain fields (e.g., home address) from public disclosure.
- Web scraping of state board portals raises ToS risk; most state websites have standard government terms prohibiting automated access without permission.
- **Recommended path:** FOIA bulk download refreshed monthly + manual spot-check for real-time flags. Counsel should confirm FOIA data is usable in consumer reports under both Path A and Path B.
- Risk tier for state boards is uniformly **T2** unless a board has an explicit API (upgrades to T1) or an explicit prohibition on commercial use (downgrades to T3).

| # | State | Board Name | Website | Integration | Risk Tier | CRA Use Permitted | Notes | Legal Sign-Off |
|---|-------|-----------|---------|-------------|-----------|-------------------|-------|----------------|
| S1 | Alabama | Alabama Board of Medical Examiners | albme.org | FOIA + Scrape | **T2** | Unknown | Standard state board; no public API. FOIA path for bulk. | ☐ Pending |
| S2 | Alaska | Alaska State Medical Board | commerce.alaska.gov/web/cbpl/ProfessionalLicensing/StateMedicalBoard | FOIA + Scrape | **T2** | Unknown | License lookup tool available online. No public API. | ☐ Pending |
| S3 | Arizona | Arizona Medical Board | azmd.gov | FOIA + Scrape | **T2** | Unknown | Public license verification available. History of disciplinary orders publicly posted. | ☐ Pending |
| S4 | Arkansas | Arkansas State Medical Board | armedicalboard.org | FOIA + Scrape | **T2** | Unknown | License lookup and disciplinary actions publicly posted. No API. | ☐ Pending |
| S5 | California | Medical Board of California | mbc.ca.gov | FOIA + Scrape | **T2-T3** | Unknown | Website ToS prohibits automated scraping. High-value state — FOIA bulk is likely the required path. CA also has CCPA obligations that may affect how CA provider data is stored and reported. Counsel priority. | ☐ Pending |
| S6 | Colorado | Colorado Medical Board | dora.colorado.gov/dpo/MedicalBoard | FOIA + Scrape | **T2** | Unknown | Disciplinary actions posted publicly. No public API. | ☐ Pending |
| S7 | Connecticut | Connecticut Medical Examining Board | portal.ct.gov/DPH/Medical-Quality/Boards/CT-Medical-Examining-Board | FOIA + Scrape | **T2** | Unknown | License verification available online. No public API. | ☐ Pending |
| S8 | Delaware | Delaware Board of Medical Licensure and Discipline | delpros.delaware.gov | FOIA + Scrape | **T2** | Unknown | Online license lookup available. No API. | ☐ Pending |
| S9 | DC | DC Board of Medicine | dchealth.dc.gov/page/board-medicine | FOIA + Scrape | **T2** | Unknown | License lookup available. No API. DC FOIA laws apply. | ☐ Pending |
| S10 | Florida | Florida Department of Health — MQA | flhealthsource.gov | FOIA + Scrape | **T2** | Unknown | MQA Online has a public license search. FL has a public records law (Sunshine Law) — FOIA equivalent is straightforward. High-volume state, priority for Phase 2. | ☐ Pending |
| S11 | Georgia | Georgia Composite Medical Board | medicalboard.georgia.gov | FOIA + Scrape | **T2** | Unknown | License search and disciplinary orders public. No API. | ☐ Pending |
| S12 | Hawaii | Hawaii Medical Board | cca.hawaii.gov/pvl/boards/medical/ | FOIA + Scrape | **T2** | Unknown | License lookup online. No API. | ☐ Pending |
| S13 | Idaho | Idaho State Board of Medicine | bom.idaho.gov | FOIA + Scrape | **T2** | Unknown | License verification online. No API. | ☐ Pending |
| S14 | Illinois | Illinois Dept. of Financial and Professional Regulation | idfpr.illinois.gov | FOIA + Scrape | **T2** | Unknown | License lookup available. IDFPR covers multiple healthcare professions. No public API known. | ☐ Pending |
| S15 | Indiana | Indiana Medical Licensing Board | in.gov/pla | FOIA + Scrape | **T2** | Unknown | PLA manages medical licenses. Online lookup available. No API. | ☐ Pending |
| S16 | Iowa | Iowa Board of Medicine | medicalboard.iowa.gov | FOIA + Scrape | **T2** | Unknown | License search online. Disciplinary actions posted. No API. | ☐ Pending |
| S17 | Kansas | Kansas Board of Healing Arts | ksbha.org | FOIA + Scrape | **T2** | Unknown | License lookup available. No public API. | ☐ Pending |
| S18 | Kentucky | Kentucky Board of Medical Licensure | kbml.ky.gov | FOIA + Scrape | **T2** | Unknown | License search online. No API. | ☐ Pending |
| S19 | Louisiana | Louisiana State Board of Medical Examiners | lsbme.la.gov | FOIA + Scrape | **T2** | Unknown | License lookup and disciplinary history online. No API. | ☐ Pending |
| S20 | Maine | Maine Board of Licensure in Medicine | maine.gov/md | FOIA + Scrape | **T2** | Unknown | License verification available. No API. | ☐ Pending |
| S21 | Maryland | Maryland Board of Physicians | mbp.state.md.us | FOIA + Scrape | **T2** | Unknown | Public license search. Disciplinary actions posted. No API known. | ☐ Pending |
| S22 | Massachusetts | MA Board of Registration in Medicine | mass.gov/orgs/board-of-registration-in-medicine | FOIA + Scrape | **T2** | Unknown | Online physician profile system. One of the more detailed state board systems. No public API. | ☐ Pending |
| S23 | Michigan | Michigan Board of Medicine | michigan.gov/lara | FOIA + Scrape | **T2** | Unknown | LARA license lookup covers medical licenses. No API. | ☐ Pending |
| S24 | Minnesota | Minnesota Board of Medical Practice | mn.gov/boards/medical-practice | FOIA + Scrape | **T2** | Unknown | License lookup online. Disciplinary actions public. No API. | ☐ Pending |
| S25 | Mississippi | Mississippi State Board of Medical Licensure | msbml.ms.gov | FOIA + Scrape | **T2** | Unknown | License lookup available. No API. | ☐ Pending |
| S26 | Missouri | Missouri State Board of Registration for the Healing Arts | pr.mo.gov | FOIA + Scrape | **T2** | Unknown | License search online. No API. | ☐ Pending |
| S27 | Montana | Montana Board of Medical Examiners | boards.bsd.dli.mt.gov/med | FOIA + Scrape | **T2** | Unknown | License lookup available. Small volume state. No API. | ☐ Pending |
| S28 | Nebraska | Nebraska DHHS — Medical Licensure | dhhs.ne.gov/licensure | FOIA + Scrape | **T2** | Unknown | License lookup via DHHS. No API. | ☐ Pending |
| S29 | Nevada | Nevada State Board of Medical Examiners | medboard.nv.gov | FOIA + Scrape | **T2** | Unknown | License lookup online. Disciplinary actions posted. No API. | ☐ Pending |
| S30 | New Hampshire | NH Board of Medicine | oplc.nh.gov/medicine | FOIA + Scrape | **T2** | Unknown | License lookup via OPLC. No API. | ☐ Pending |
| S31 | New Jersey | NJ State Board of Medical Examiners | njconsumeraffairs.gov/bme | FOIA + Scrape | **T2** | Unknown | Online license verification. No API. | ☐ Pending |
| S32 | New Mexico | New Mexico Medical Board | nmmedicalboard.org | FOIA + Scrape | **T2** | Unknown | License lookup online. No API. | ☐ Pending |
| S33 | New York | NY Office of the Professions (NYSED) | op.nysed.gov | FOIA + Scrape | **T2-T3** | Unknown | High-volume, high-priority state. Website terms restrict automated access. FOIL (NY FOIA equivalent) is the required bulk path. Counsel: confirm FOIL data usability in consumer reports. | ☐ Pending |
| S34 | North Carolina | North Carolina Medical Board | ncmedboard.org | FOIA + Scrape | **T2** | Unknown | License search and disciplinary history public. No API. | ☐ Pending |
| S35 | North Dakota | North Dakota Board of Medicine | ndbom.org | FOIA + Scrape | **T2** | Unknown | License lookup online. Small volume state. No API. | ☐ Pending |
| S36 | Ohio | State Medical Board of Ohio | med.ohio.gov | FOIA + Scrape | **T2** | Unknown | Online license lookup. Disciplinary actions published. No API. | ☐ Pending |
| S37 | Oklahoma | Oklahoma State Board of Medical Licensure and Supervision | osbmls.ok.gov | FOIA + Scrape | **T2** | Unknown | License lookup online. No API. | ☐ Pending |
| S38 | Oregon | Oregon Medical Board | oregon.gov/omb | FOIA + Scrape | **T2** | Unknown | License lookup and disciplinary actions public. No API. | ☐ Pending |
| S39 | Pennsylvania | PA State Board of Medicine | dos.pa.gov/ProfessionalLicensing/BoardsCommissions/Medicine | FOIA + Scrape | **T2** | Unknown | License verification online. No API known. | ☐ Pending |
| S40 | Rhode Island | RI Board of Medical Licensure and Discipline | health.ri.gov/licensing | FOIA + Scrape | **T2** | Unknown | License lookup online. Small volume state. No API. | ☐ Pending |
| S41 | South Carolina | SC Board of Medical Examiners | llr.sc.gov/med.aspx | FOIA + Scrape | **T2** | Unknown | License lookup online. No API. | ☐ Pending |
| S42 | South Dakota | SD Board of Medical and Osteopathic Examiners | sdbmoe.gov | FOIA + Scrape | **T2** | Unknown | License lookup available. Small volume state. No API. | ☐ Pending |
| S43 | Tennessee | Tennessee Board of Medical Examiners | tn.gov/health/health-program-areas/health-professional-boards/me-board.html | FOIA + Scrape | **T2** | Unknown | License lookup via TN DOH. No API. | ☐ Pending |
| S44 | Texas | Texas Medical Board | tmb.state.tx.us | FOIA + Scrape | **T2-T3** | Unknown | High-volume, high-priority state. TMB website terms restrict automated access. TMB does provide data downloads under public information law. Counsel: confirm whether TMB data downloads are permissible in consumer reports. | ☐ Pending |
| S45 | Utah | Utah Division of Professional Licensing | dopl.utah.gov | FOIA + Scrape | **T2** | Unknown | DOPL license lookup covers medical licenses. No API. | ☐ Pending |
| S46 | Vermont | Vermont Board of Medical Practice | healthvermont.gov/health-professionals-systems/board-medical-practice | FOIA + Scrape | **T2** | Unknown | License lookup online. Small volume state. No API. | ☐ Pending |
| S47 | Virginia | Virginia Board of Medicine | dhp.virginia.gov/medicine | FOIA + Scrape | **T2** | Unknown | License lookup via DHP. Disciplinary actions public. No API. | ☐ Pending |
| S48 | Washington | Washington Medical Commission | wmc.wa.gov | FOIA + Scrape | **T2** | Unknown | License verification and disciplinary orders online. No API. | ☐ Pending |
| S49 | West Virginia | West Virginia Board of Medicine | wvbom.wv.gov | FOIA + Scrape | **T2** | Unknown | License lookup online. Small volume state. No API. | ☐ Pending |
| S50 | Wisconsin | Wisconsin Medical Examining Board | dsps.wi.gov | FOIA + Scrape | **T2** | Unknown | DSPS license lookup covers medical licenses. No API. | ☐ Pending |
| S51 | Wyoming | Wyoming Board of Medicine | wyomedboard.wy.gov | FOIA + Scrape | **T2** | Unknown | License lookup online. Small volume state. No API. | ☐ Pending |

### Supplemental State Board Sources

| # | Source | Data Provided | Integration | Risk Tier | Notes | Legal Sign-Off |
|---|--------|--------------|-------------|-----------|-------|----------------|
| S52 | **FSMB DocInfo** (Federation of State Medical Boards) | Aggregated license and disciplinary data across all 50 states + DC | Licensed | **T3** | FSMB aggregates data from all state boards into a single API/database. Requires a commercial data license — pricing and terms not public. This could replace individual state board scraping for licensing data. Counsel: confirm whether FSMB license permits CRA use and whether the data provenance is auditable for FCRA § 1681e(b) accuracy requirements. | ☐ Pending |
| S53 | **ABMS Board Certification** (American Board of Medical Specialties) | Board certification status, specialty, year certified | Licensed / Manual | **T3** | ABMS offers a public verification tool ($15/lookup) and enterprise API access. ToS restricts bulk commercial use without a license agreement. Counsel: confirm whether ABMS certified-physician database is licensable for CRA use. | ☐ Pending |

---

## 3. Court Records

| # | Source | Data Provided | Integration | ToS / Policy URL | Risk Tier | CRA Use Permitted | ToS Notes | Legal Sign-Off |
|---|--------|--------------|-------------|-----------------|-----------|-------------------|-----------|----------------|
| C1 | **PACER** (federal courts — all districts) | Federal civil/criminal dockets, case filings, judgments | PACER | https://pacer.uscourts.gov/register-account/pacer-terms-conditions | **T2** | Likely yes — public court records | PACER provides public access to federal court records at $0.10/page (fee waived under $30/quarter). ToS permits data retrieval for legitimate purposes. Re-publishing court data in consumer reports is an unsettled area — counsel should confirm. PACER API (CM/ECF) available for programmatic access. Scraping PACER is restricted by ToS. | ☐ Pending |
| C2 | **CourtListener / RECAP Archive** (Free Law Project) | Federal court documents, dockets, opinions (subset of PACER) | API-Free + Bulk-DL | https://www.courtlistener.com/api/ | **T2** | Likely yes — open license | Free Law Project provides CC0/open licensed access to a large subset of federal court data. Reduces PACER costs. Counsel: confirm whether using CourtListener as a PACER proxy creates any provenance issue for FCRA accuracy requirements. | ☐ Pending |
| C3 | **California Courts (CCMS/eCourt)** | CA civil and criminal case records | Scrape / Manual | https://www.courts.ca.gov | **T3** | Unknown | CA courts have no unified public API. Individual court lookups are manual. Automated access varies by county. CA has specific rules about expungement and sealing that must be respected. Counsel priority. | ☐ Pending |
| C4 | **New York Courts (NYCOURTS / eCourts)** | NY civil and criminal case records | Scrape / Manual | https://iapps.courts.state.ny.us/webcivil/ecourtsMain | **T3** | Unknown | NY eCourts has limited public access. No bulk API. NY has specific sealing statutes (CPL § 160.50, § 160.55) that restrict re-reporting of certain records. Counsel priority. | ☐ Pending |
| C5 | **Texas Courts (eFileTexas / Tyler Technologies)** | TX civil case records, some criminal | API + Scrape | https://search.txcourts.gov | **T2-T3** | Unknown | Texas has a public court records search. Some counties use Tyler Technologies Odyssey platform which has an API. TX expunction law (CCP Art. 55.01) restricts re-reporting expunged records. | ☐ Pending |
| C6 | **Florida Courts (Clerk of Courts)** | FL civil and criminal records (county-level) | Scrape / Manual | Varies by county | **T2-T3** | Unknown | FL courts are county-operated. No statewide unified system. FL has broad public records law (Sunshine Law) but also specific sealing/expungement statutes. Coverage varies significantly by county. | ☐ Pending |
| C7 | **Illinois Courts (eFileIL / Clerk)** | IL civil and criminal records | Scrape / Manual | https://www.illinoiscourts.gov | **T2-T3** | Unknown | No statewide public API. County-level access varies. Cook County (Chicago) has some online access. | ☐ Pending |
| C8 | **State Court Systems — Remaining 45 States** | Civil and criminal records | Scrape / FOIA / Manual | Varies by state | **T2-T3** | Unknown | Access model varies dramatically by state. Roughly 15 states have some form of public online access; the remainder require in-person or FOIA-based access. Counsel should advise on which states' court data is reportable and whether a phased state-by-state rollout approach is adequate for Phase 3. Engineering note: court adapter complexity is substantially higher than state board adapters. | ☐ Pending |

---

## 4. Commercial Directory Sources

| # | Source | Data Provided | Integration | ToS URL | Risk Tier | CRA Use Permitted | ToS Notes | Legal Sign-Off |
|---|--------|--------------|-------------|---------|-----------|-------------------|-----------|----------------|
| D1 | **Ribbon Health** | Provider directory data: demographics, specialties, affiliations, insurance networks, location | Licensed | https://ribbonhealth.com/terms | **T3** | Unknown — requires contract review | Ribbon Health is a B2B provider data company. Access requires a commercial data license. CRA use clause must be explicitly negotiated. This is the architecture's primary commercial directory source — contract terms are critical. Engineering cannot scope C10 adapters for this source until a license is in place. | ☐ Pending |
| D2 | **Healthgrades** | Provider profiles, patient ratings, board certifications, hospital affiliations, malpractice data | T4 | https://www.healthgrades.com/about/terms-of-use | **T4** | Unknown — likely prohibited without contract | Healthgrades ToS explicitly prohibits scraping, automated access, and commercial re-use of provider data without written permission. A licensed data agreement would be required. Healthgrades has enforcement history against scrapers. Counsel: assess whether a licensed data agreement is available and whether it permits CRA use. | ☐ Pending |
| D3 | **Vitals** (WebMD Health Corp.) | Provider profiles, patient reviews, education, hospital affiliations | **T4** | https://www.vitals.com/terms-of-use | **T4** | Unknown — likely prohibited without contract | Vitals ToS prohibits automated access and commercial re-use. Owned by WebMD (Internet Brands). Licensed data agreement would be required. Similar risk profile to Healthgrades. Counsel: assess whether a licensed data agreement is available and whether it permits CRA use. | ☐ Pending |
| D4 | **Doximity** | Provider professional profiles, education, publications, hospital affiliations, peer ratings | **T4** | https://www.doximity.com/terms | **T4** | Likely prohibited — ToS restricts data export | Doximity ToS explicitly prohibits scraping, data harvesting, and use of profile data for commercial purposes without written consent. No public API for provider data access. Counsel: assess whether a partner API or data license is available, and whether CRA or non-CRA use would be permissible. If unavailable, this source may need to be removed from the architecture. | ☐ Pending |

---

## 5. Review Platforms

| # | Source | Data Provided | Integration | ToS / API Policy URL | Risk Tier | CRA Use Permitted | ToS Notes | Legal Sign-Off |
|---|--------|--------------|-------------|---------------------|-----------|-------------------|-----------|----------------|
| R1 | **Google Places API** (Google Maps Platform) | Provider location, ratings, review count, business status, hours | API | https://developers.google.com/maps/terms | **T2** | Unknown — requires license review | Google Maps Platform ToS permits commercial use of Places data via the API. However, ToS prohibits: (1) caching data beyond 30 days, (2) using data to create a competing mapping service, (3) displaying data without Google attribution. Aggregating provider ratings for consumer reports may be permissible but counsel should confirm whether using Google review data as a component of a consumer report violates the ToS's restrictions on "creating independent datasets." CRA use clause is not addressed in standard ToS. | ☐ Pending |
| R2 | **Yelp Fusion API** | Business ratings, review count, categories, hours | API | https://www.yelp.com/developers/api_terms | **T2** | Unknown — requires license review | Yelp Fusion API ToS permits commercial use. Key restrictions: (1) must display Yelp branding and link back to Yelp, (2) may not cache data for more than 24 hours for most endpoints, (3) may not use data to "compete with Yelp." Aggregating Yelp ratings in consumer reports is a gray area. Counsel: confirm whether the 24-hour cache restriction is compatible with async report generation architecture and whether inclusion in a provider report constitutes competition with Yelp. | ☐ Pending |

---

## 6. Insurance Network Sources

| # | Source | Data Provided | Integration | ToS / Policy URL | Risk Tier | CRA Use Permitted | ToS Notes | Legal Sign-Off |
|---|--------|--------------|-------------|-----------------|-----------|-------------------|-----------|----------------|
| I1 | **CMS Medicare Physician Fee Schedule / Provider Enrollment** | Medicare participation status, accepted assignment, provider type | API-Free + Bulk-DL | https://data.cms.gov/provider-data | **T1** | Likely yes — CC0 license | data.cms.gov data is CC0 licensed. Medicare participation status is public federal data. Includes Opt-Out providers (important negative signal). | ☐ Pending |
| I2 | **CMS Medicaid Provider Enrollment** | Medicaid participation by state | API-Free + Bulk-DL | https://data.medicaid.gov | **T1** | Likely yes — CC0 license | Medicaid provider data is public federal data, CC0. State-level Medicaid enrollment data is available. | ☐ Pending |
| I3 | **Licensed Insurance Network Directories** (commercial insurers: Aetna, BCBS, Cigna, UHC, etc.) | In-network participation by plan and geography | Licensed | Varies by carrier | **T4** | Unknown — contract required per carrier | Major commercial insurers maintain proprietary network directories. No public API. Bulk data access requires a commercial data agreement with each carrier. Network participation data is highly valuable but requires negotiated contracts. Counsel: advise on strategy — (a) negotiate carrier-by-carrier, (b) use a data aggregator (e.g., Ribbon Health already includes some network data), or (c) limit to CMS-covered networks only for MVP. | ☐ Pending |
| I4 | **NPPES NPI + CMS specialty crosswalk** (proxy for network inference) | Specialty + taxonomy can proxy for likely network participation | API-Free + Bulk-DL | https://data.cms.gov | **T1** | Likely yes | NPPES taxonomy codes can be used as a proxy signal for specialty-based network inference. Not direct network data, but a useful derived signal when licensed network data is unavailable. | ☐ Pending |

---

## 7. Academic and Professional Sources

| # | Source | Data Provided | Integration | ToS / Policy URL | Risk Tier | CRA Use Permitted | ToS Notes | Legal Sign-Off |
|---|--------|--------------|-------------|-----------------|-----------|-------------------|-----------|----------------|
| A1 | **PubMed / NCBI Entrez API** (NIH/NLM) | Published research papers, clinical trial participation, author affiliations, citation counts | API-Free | https://www.ncbi.nlm.nih.gov/home/about/policies/ | **T1** | Likely yes — public federal data | NIH/NLM data is explicitly public domain. Entrez API has no terms restricting commercial use or aggregation. Rate limits apply (10 req/sec without API key, 3/sec without). High-value signal for research-active physicians. | ☐ Pending |
| A2 | **ClinicalTrials.gov** (NIH) | Clinical trial investigator records, trial status, sponsor | API-Free + Bulk-DL | https://clinicaltrials.gov/ct2/about-site/terms-conditions | **T1** | Likely yes — public federal data | ClinicalTrials.gov data is public domain, no known restriction on aggregation. Useful for identifying research-active clinicians. | ☐ Pending |
| A3 | **Doximity** | (See D4 above) | — | — | **T4** | Likely prohibited | See row D4. Listed here as well since it is classified as an academic/professional source in the architecture. | ☐ Pending |

---

## 8. Source Count Summary

| Category | Sources | T1 | T2 | T3 | T4 |
|----------|---------|----|----|----|----|
| Federal Government | 6 | 4 | 2 | 0 | 0 |
| State Medical Boards | 53 (51 boards + FSMB + ABMS) | 0 | 51 | 2 | 0 |
| Court Records | 8 | 0 | 2 | 5 | 0 |
| Commercial Directories | 4 | 0 | 0 | 1 | 3 |
| Review Platforms | 2 | 0 | 2 | 0 | 0 |
| Insurance Networks | 4 | 2 | 0 | 0 | 1 |
| Academic/Professional | 3 | 2 | 0 | 0 | 1 |
| **Total** | **80** | **8** | **57** | **8** | **5** |

**T1 sources (8):** Immediately usable post-legal gate (pending counsel confirmation).
**T2 sources (57):** Largest category — primarily state medical boards via FOIA path. Likely permissible, but each requires individual counsel review.
**T3 sources (8):** Require contract negotiation or explicit license. Ribbon Health and FSMB DocInfo are the highest-priority T3 sources.
**T4 sources (5):** Healthgrades, Vitals, Doximity, Doximity (dup), commercial insurer networks. These may require significant contract work or architectural removal.

---

## 9. Priority Sources for Legal Counsel Review

In order of business impact, counsel should prioritize:

1. **NPPES + OIG LEIE + SAM.gov + CMS Care Compare (F1-F4)** — Foundation of any report. Confirm T1 status for CRA path.
2. **State medical boards via FOIA (S1-S51)** — Core data source. Confirm FOIA bulk data is reportable under both Path A and B.
3. **PACER / federal court records (C1-C2)** — High value for disciplinary/malpractice signals. Confirm re-reporting is permissible.
4. **Ribbon Health (D1)** — Primary commercial directory. Contract must be in place and must include CRA use clause if Path A.
5. **Google Places API (R1)** — Ratings aggregation. Confirm 30-day cache window and report inclusion are permissible.
6. **Yelp Fusion API (R2)** — Ratings aggregation. Confirm 24-hour cache restriction does not conflict with async architecture.
7. **Healthgrades + Vitals (D2, D3)** — Confirm whether licensed data agreements are available and on what terms.
8. **Doximity (D4 / A3)** — High value but T4. Early determination needed — if unavailable, remove from architecture.
9. **NPDB (F6)** — Confirm whether public file aggregate signals + individual queries (via eligible entity status) are feasible.
10. **DEA registration (F5)** — Confirm FOIA path or alternative for bulk validation.

---

## 10. Questions for Legal Counsel

1. **FOIA data in consumer reports:** Is data obtained via FOIA/public records requests from state medical boards permissible in a consumer report under both Path A (CRA) and Path B (Non-CRA)?

2. **Web scraping risk independent of FCRA:** Even if the underlying data is public, does automated scraping of a state board or court website — in violation of that site's ToS — create independent legal risk (CFAA, tortious interference, breach of ToS)?

3. **Court record expungement compliance:** What is the engineering obligation for removing expunged, sealed, or juvenile records from the system after they have already been ingested? Who is responsible for monitoring expungement orders post-ingestion?

4. **NPDB eligible entity status:** Can this platform qualify as an "eligible entity" under 45 CFR Part 60 to query individual NPDB records? If not, is the Public Use File (aggregate only) the only permissible path?

5. **Google / Yelp cache restrictions:** The async report generation pipeline may cache source data for up to 24 hours for performance. Does this conflict with Yelp's 24-hour cache restriction? Is there a permissible architecture that avoids the conflict?

6. **Commercial directory licensing for CRA:** For Healthgrades, Vitals, and Doximity — is it likely that any commercial data agreement for these sources would permit CRA use? Or should engineering assume these sources are excluded from Path A?

7. **Insurance network data strategy:** Should the architecture rely on NPPES/CMS data as a proxy for network participation, or is it feasible to negotiate carrier-by-carrier agreements at the MVP stage?

8. **State-specific restrictions beyond FCRA:** Are there states (beyond CA and NY, which are flagged in this matrix) where state law creates independent restrictions on aggregating or re-reporting healthcare provider data?

---

*This matrix will be versioned as `tos-matrix-v1.md` after legal counsel completes initial review. The "Legal Sign-Off" column will be populated with counsel's determination and date for each source.*
