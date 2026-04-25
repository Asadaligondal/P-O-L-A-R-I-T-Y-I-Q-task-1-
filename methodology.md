# Data Methodology — Family Office Dataset
**PolarityIQ Differentiator Assessment | Task 1**

---

## Overview

The goal was to build a validated dataset of 50 real family office records that could serve as the foundation for a queryable RAG pipeline. This document covers how I found the data, how I enriched it, how I validated it, what broke along the way, and what I would do differently with more time.

This is not a clean story. Several approaches failed or produced low-quality results. I am documenting those as honestly as the successes because the failure modes are as informative as what worked.

---

## 1. Discovery Approach

### What I Tried First (and Why It Partially Failed)

**SEC EDGAR IAPD** was the intended primary source. The theory: family offices managing over $110M that are registered as investment advisers file Form ADV, which is public. Search for "family office" in firm names → get a list of real entities with AUM, principals, and addresses.

The reality: most true single-family offices are *exempt* from SEC registration under the 2011 Family Office Rule (if they serve a single family and don't hold themselves out as investment advisers). The ones that show up on EDGAR tend to be the larger, more institutionalised offices or multi-family offices. The most valuable and secretive SFOs — exactly the kind PolarityIQ's clients want to reach — are not there.

What EDGAR *is* good for: confirming entities that you already found elsewhere. I used it to verify Soros Fund Management (CRD: 106706) and to check whether entities matched known descriptions.

**Form D filings** (private fund raises) were useful as a signal layer — family offices sometimes file Form D when structuring a vehicle. But this requires cross-referencing entity names back to EDGAR, which is time-consuming at scale.

### What Actually Worked

**Eagle Private (eagle-private.com)** published a January 2026 report on the top 20 single family offices globally. This was the highest-quality single source I found — structured data with AUM estimates, principal names, HQ locations, investment profiles, and recent activity for each office. Crucially, it cited its own sources (Bloomberg Wealth, Forbes, annual reports, stock exchange filings), which gave me a validation path.

**Axial.net** has a directory of 546 family offices that have been active in lower-middle-market M&A. These are not the $100B trophy offices — they are real, operating family offices that have closed verified deals. The deal history on Axial functions as an activity signal: an office that closed 14 deals is demonstrably real and active, even if the principal is anonymous.

**Crunchbase** provided investment signals for the larger, tech-adjacent offices (Bezos Expeditions, Mousse Partners). When a family office backs a startup, Crunchbase often captures it with date and round size.

**SEC 13F filings** were used for offices large enough to file ($100M+ in public equity holdings). Cascade Investment LLC files 13F, which means its public equity holdings are disclosed quarterly. This is the most reliable data in the entire dataset.

**Press releases and financial news** (BusinessWire, PRNewswire, FT, Bloomberg) filled the recent signals column. When a family office makes a notable investment or hire, it sometimes surfaces in press. These are high-confidence signals because they are independently published and dateable.

### Sources That Did Not Work

- **FINTRX**: Paywalled. Free tier does not expose meaningful data.
- **Campden Wealth reports**: The full reports are paid. Public summaries gave context but not individual records.
- **Direct email discovery**: No family office publishes contact emails on public websites. Hunter.io pattern-guessing is unreliable for private entities. I did not include guessed emails — they would have degraded dataset quality.
- **Generic Google search for "family office list"**: Returns SEO-optimised aggregators with recycled, unverified data. These were cross-references only, never primary sources.

---

## 2. Schema Design Decisions

I chose 19 fields. The key design decisions:

**Confidence Score + Confidence Reason as separate fields.** A single confidence label without explanation is useless. The reason field forces me to articulate exactly what was and was not verified — and it gives downstream users (and the RAG system) a way to weight answers appropriately.

**Recent Signals as a text field with dates embedded.** Rather than separating "last investment" into its own column, I embedded signal text with approximate dates ("Acquired MoneyThumb, Aug 2024"). This is intentional — it makes the signals readable in a RAG chunk without requiring JOIN-style reasoning.

**AUM as a text range, not a number.** Family office AUM is almost never a precise figure. "$90-100B" is more honest than "$95B". Downstream, this required building an AUM tier extraction layer for the RAG pipeline (see Section 4).

**Notes / Caveats as a mandatory field.** Every record has something that could not be verified. Requiring a notes field prevents the false confidence that comes from leaving it blank.

---

## 3. Enrichment Process

Records went through three enrichment passes:

**Pass 1 — Structural enrichment.** For each discovered entity, I looked for: legal name, HQ location, FO type (SFO vs MFO), AUM estimate, and investment focus. Sources: Eagle Private, Axial profiles, SEC filings.

**Pass 2 — Human layer enrichment.** For each entity, I searched LinkedIn for the principal named in the primary source. If confirmed (title matches, employer matches, profile is current), the LinkedIn URL was recorded. If not findable or not matchable, "Undisclosed" was recorded. I did not assume the first LinkedIn result was correct.

**Pass 3 — Signal enrichment.** For each entity, I ran a targeted news search: "[FO name] investment 2024" and "[FO name] acquisition 2025". Any result that cited a specific investment with a date was added to the Recent Signals field. Undated or vague signals were excluded.

**What the enrichment script added.** After building the initial dataset, I ran an automated completeness scoring script that flagged records with fewer than 8/19 fields populated. These became candidates for additional enrichment. The script also normalized AUM text into tiered buckets (for the RAG metadata layer) and flagged inconsistent city/country formatting.

---

## 4. Confidence Framework

Three tiers, applied consistently:

**HIGH:** Two or more independent sources confirmed the same data point. The entity is real, the principal is named, and at least one signal is dateable and specific. The validation path is reproducible — I can give you a URL that confirms every HIGH-confidence field.

**MEDIUM:** One source confirmed, one inferred. The entity exists and is active, but some fields (AUM, email, check size) are estimated rather than confirmed. The principal may be named in only one source.

**LOW:** The record is sourced from a single directory (primarily Axial) where the family office self-describes. The deal history confirms activity, but no independent source has verified the principal name, AUM, or investment mandate. These records are real family offices — the deal history proves that — but they are not fully documented.

**Distribution in the final dataset:**
- HIGH confidence: 16 records
- MEDIUM confidence: 18 records  
- LOW confidence: 19 records

**Validation script output (validate.py):**
- Total records: 53
- LinkedIn URLs checked: 8 (1 second delay between requests)
- LinkedIn broken: 0
- Needs enrichment (completeness score < 0.5): 24
- Confidence mismatch: 0
- Passed all checks: 29

The 24 flagged for enrichment are expected — these are the Axial-sourced mid-market records missing principal names, emails, and AUM. The flags are not failures; they are honest documentation of what the open-source research process can and cannot find. Every flagged record has a deal history that confirms it is real and active.

This distribution is intentional. A dataset with 50 HIGH confidence records would either be fabricated or extremely expensive to produce. The honest answer is that private family office data is partially opaque by design.

---

## 5. Known Limitations

**AUM is almost always an estimate.** Family offices are not required to disclose AUM unless they register as investment advisers. Even registered advisers often underreport. Treat all AUM figures as indicative ranges, not audited figures.

**The most secretive SFOs are not in this dataset.** There are family offices managing multi-generational industrial wealth that have no digital footprint whatsoever. They do not appear in EDGAR, LinkedIn, Crunchbase, or press. They cannot be found through open-source intelligence. This dataset reflects the discoverable universe, which is not the same as the complete universe.

**Contact data is thin.** Emails are almost never publicly available for family offices. LinkedIn URLs are included where confirmed, but principals at private family offices frequently have minimal or private LinkedIn profiles.

**Axial LOW-confidence records lack principal attribution.** Approximately 15 records have no named principal because Axial profiles do not require this. The deal history is the primary verification signal for these records.

**Signal freshness varies.** Some signals are from 2025, some from 2023. The dataset includes a `last_validated` date but individual signals may be older than that date.

---

## 6. What I Would Do With More Time

**Automated SEC EDGAR monitoring.** New Form ADV filings can be scraped via the SEC bulk data API. A scheduled job that pulls new "family office" registrations weekly would keep the dataset fresh without manual work.

**Apollo.io or Hunter.io integration for email discovery.** These tools use domain pattern inference to suggest professional emails. For confirmed entities with known domains, this would fill the contact gap — with appropriate LOW confidence tagging.

**News API for signal automation.** The current signals were found manually. A pipeline that runs each FO name through a news API (NewsAPI, GDELT) on a weekly cadence would automate freshness without manual review.

**AUM normalisation to numeric tiers.** The text AUM field required a custom extraction layer for the RAG pipeline. Proper normalisation upfront — storing both the raw text ("$90-100B") and a numeric midpoint (95) — would make filtering cleaner.

**Cross-validation against PitchBook or Preqin.** Both platforms have structured family office databases. A comparison between this open-source dataset and a commercial one would quantify the coverage gap and identify which record types are hardest to find through open sources.
