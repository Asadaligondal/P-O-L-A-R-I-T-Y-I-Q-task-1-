# Validation Chains — 3 Selected Records
**PolarityIQ Differentiator Assessment | Task 1**

Three records selected to demonstrate the full validation process across all three confidence tiers. Each chain documents discovery source, extraction method, enrichment steps, validation logic, and honest confidence assessment.

---

## Record 1 — Soros Fund Management LLC
**Confidence: HIGH**

---

### Discovery

Found via SEC EDGAR IAPD firm search. Searched "Soros" in firm name field. Returned "Soros Fund Management LLC" as an active registered investment adviser.

EDGAR direct link: `https://adviserinfo.sec.gov/firm/summary/106706`

CRD Number: **106706**
SEC Number: **801-56064**

### Extraction

From the ADV Part 1A filing:
- **Legal name:** Soros Fund Management LLC
- **HQ address:** 250 West 55th Street, New York, NY 10019
- **Registration status:** SEC Registered
- **AUM (Form ADV Item 5):** Reported as approximately $25-28B (ranges across filing years; $28B cited in 2023 filing)
- **Clients:** Very few (consistent with family office — serves only the Soros family and related entities)
- **Schedule A (direct owners):** Lists George Soros as indirect owner; Alexander Soros identified as Chairman in 2023 transition

From the ADV filing footnotes:
> Soros Fund Management converted from a public hedge fund to a family office structure in 2011 following return of external investor capital.

This conversion is independently documented in a 2011 Wall Street Journal report and confirmed in Bloomberg Wealth.

### Enrichment Steps

**Step 1 — Principal confirmation:**
Searched LinkedIn for "Alexander Soros" + "Soros Fund Management." Profile exists, title listed as Chairman. Employer matches. Profile appears current (activity visible in 2024-25). LinkedIn URL recorded.

**Step 2 — Investment signal search:**
Google search: `"Soros Fund Management" investment 2024 site:bloomberg.com OR site:reuters.com`

Results confirmed:
- Continued macro and geopolitical thematic investments in 2024
- 13F filings (public equity positions) filed quarterly with SEC — confirms ongoing active management
- Alexander Soros' public statements on investment philosophy covered in Bloomberg (2023-24)

**Step 3 — AUM cross-validation:**
SEC ADV AUM figure cross-checked against Eagle Private 2026 report which cites "$25-28B." Both aligned. Forbes Billionaires list (George Soros) consistent with this range.

**Step 4 — Entity type confirmation:**
ADV filing explicitly states the firm manages assets for a single family (the Soros family). Client count is in single digits. This confirms SFO classification.

### Validation Logic

| Field | Verified | Source | Notes |
|---|---|---|---|
| Legal name | ✅ | SEC EDGAR | Exact legal entity name from CRD 106706 |
| HQ address | ✅ | SEC EDGAR ADV | 250 W 55th St, New York |
| AUM range | ✅ | SEC ADV + Eagle Private | Both cite $25-28B |
| Principal name | ✅ | SEC Schedule A + LinkedIn | Alexander Soros confirmed |
| FO type (SFO) | ✅ | SEC ADV client count | Single-digit clients = SFO |
| Investment focus | ✅ | Bloomberg + 13F | Macro, derivatives, thematic confirmed |
| Email | ❌ | Not publicly available | Not included |
| Check size | ❌ | Not disclosed | Not applicable for SFO of this type |

### Confidence Assessment: HIGH

Every core field is verifiable via a URL that any third party can visit. The SEC ADV is a legal document — it cannot be fabricated. The principal transition to Alexander Soros is documented in multiple independent press sources. The only fields that could not be verified are email (never public for SFOs) and exact check size (not applicable at this scale).

**Reproducibility:** Anyone can verify this record in under 10 minutes using adviserinfo.sec.gov/firm/summary/106706.

---

## Record 2 — Northwoods Partners
**Confidence: MEDIUM**

---

### Discovery

Found via Axial.net family office directory, New York filter. URL: `https://www.axial.net/company/northwoods-partners`

Axial is a private deal platform where family offices and PE firms register to source lower-middle-market acquisitions. Presence on Axial is self-reported, but deal history is independently verified by Axial's platform (both counterparties confirm closed transactions).

### Extraction

From the Axial profile:
- **Entity name:** Northwoods Partners
- **Location:** New York
- **Type:** Family Office (Axial classification)
- **Description:** Founded 2022 from proceeds of ImageFIRST sale. Bernstein family office.
- **Closed deals via Axial:** 3
- **Total closed deals:** 4

From deal history:
- May 2025: Acquired "Anonymous" (counterparty name withheld by seller)
- Mar 2025: Acquired "Confidential Company"
- Apr 2023: Acquired "Anonymous"
- May 2023: Breakthrough Growth Partners → Confidential Company (related entity)

### Enrichment Steps

**Step 1 — Bernstein family / ImageFIRST verification:**
Google search: `"ImageFIRST" Bernstein family sale`

Results: ImageFIRST (healthcare linen services company) is a real company, currently owned by private equity. Multiple trade press articles confirm it was family-founded and later sold to PE. The Bernstein family founding is referenced in healthcare services industry coverage.

This confirms the origin story in the Axial profile — not fabricated.

**Step 2 — Principal search:**
LinkedIn search: `"Northwoods Partners" "family office"` and `"Bernstein" "ImageFIRST" "Northwoods"`

Found LinkedIn profiles consistent with the described background (PE/operations professionals with healthcare linen industry history) but could not confirm exact names match the Axial principals with certainty. LinkedIn connection to Northwoods Partners entity is tenuous — the company page has few followers and limited verification.

**Step 3 — AUM estimation:**
ImageFIRST sale to PE was not publicly valued. Therefore AUM cannot be estimated from the exit proceeds. Left as "Undisclosed."

**Step 4 — Activity signal:**
The 3 Axial-confirmed closed deals in 2023-2025 are the primary activity signal. These require confirmation from both buyer (Northwoods) and seller — Axial's platform records them as closed. This is the strongest verification available for mid-market FOs.

### Validation Logic

| Field | Verified | Source | Notes |
|---|---|---|---|
| Entity name | ✅ | Axial.net | Self-reported but platform-verified through deal history |
| Location | ✅ | Axial profile | New York confirmed |
| FO type | ✅ | Axial classification | Self-described + deal pattern consistent |
| Origin story (Bernstein/ImageFIRST) | ✅ (partial) | Trade press | ImageFIRST confirmed real; Bernstein founding confirmed; specific sale terms not public |
| Active deals | ✅ | Axial deal records | 4 total closed deals, 3 via Axial platform |
| Principal names | ❌ | Not publicly identified | LinkedIn search inconclusive |
| AUM | ❌ | Not estimable | Exit proceeds not publicly disclosed |
| Email | ❌ | Not available | Not public |

### Confidence Assessment: MEDIUM

The entity is real and demonstrably active — the deal history proves that. The origin story is verifiable. But the principals are not named in any public source, and AUM cannot be estimated. I know this family office exists and is active. I do not know who runs it or how much capital they deploy.

**Why not LOW:** The deal history is independently verified, not just a profile claim. That distinguishes this from a pure self-report.

**Why not HIGH:** No named principal, no AUM, no contact information independently confirmed from a source outside Axial itself.

---

## Record 3 — Aeonic Partners
**Confidence: LOW**

---

### Discovery

Found via Axial.net family office directory, New York filter. URL: `https://www.axial.net/company/aeonic-partners`

### Extraction

From the Axial profile:
- **Entity name:** Aeonic Partners
- **Location:** New York
- **Type:** Family Office (Axial self-classification)
- **Description:** Buy-and-hold strategy. Different from traditional 5-year PE cycles. Principals involved in every step. Decision-making process is streamlined.
- **Closed deals via Axial:** 1
- **Total closed deals:** 11

### Enrichment Steps

**Step 1 — Entity verification:**
Google search: `"Aeonic Partners" family office New York`

Results: Very limited. No press coverage, no LinkedIn company page with significant presence, no SEC registration found. The entity appears to operate entirely privately.

**Step 2 — Principal search:**
LinkedIn search: `"Aeonic Partners"` — Returns no clear company page. No individuals listing Aeonic Partners as employer found with confidence.

**Step 3 — SEC EDGAR search:**
Searched EDGAR for "Aeonic Partners." No matching registration found. This is consistent with a small SFO that is exempt from registration (manages a single family's capital below the threshold or qualifies for the family office exemption).

**Step 4 — Crunchbase search:**
No results for Aeonic Partners on Crunchbase. No portfolio companies or investment rounds attributed.

**Step 5 — AUM estimation:**
No basis for estimation. Not attempted.

**Step 6 — Cross-reference on deal counterparties:**
The 1 Axial-confirmed deal is the only independent signal. The other 10 "total closed deals" are self-reported by Aeonic on Axial and not independently verified by platform records.

### Validation Logic

| Field | Verified | Source | Notes |
|---|---|---|---|
| Entity name | ⚠️ | Axial self-report | No independent confirmation |
| Location | ⚠️ | Axial self-report | New York stated, not confirmed |
| FO type | ⚠️ | Axial self-classification | Consistent with description, not verified |
| Investment focus | ⚠️ | Axial self-description | Buy-and-hold stated, not confirmed by portfolio evidence |
| 1 closed deal | ✅ | Axial platform | One deal confirmed by both counterparties |
| Principal names | ❌ | Not found | No public source |
| AUM | ❌ | Not estimable | No basis |
| Email / LinkedIn | ❌ | Not found | No public presence |

### Confidence Assessment: LOW

This record is included because the Axial platform confirmed one closed deal, which means the entity transacted with a real counterparty. It is not fabricated. But essentially everything else about this record is self-reported on a single platform with no independent corroboration.

**What this record is useful for:** The buy-and-hold, long-horizon investment philosophy is described clearly and is semantically valuable in the RAG — if someone queries "family offices with patient capital in New York," Aeonic is a legitimate result even with LOW confidence.

**What this record should not be used for:** Outreach targeting, AUM estimation, or any claim about who runs the office.

**The honest question I could not answer:** Is Aeonic Partners a family office in the traditional sense (managing a single family's generational wealth), or is it a small independent sponsor that describes itself as a family office? The profile language is consistent with either. Without a named family or verifiable principal, I cannot resolve this.

This ambiguity is itself important to document — it reveals a real problem with self-reported directories as data sources.
