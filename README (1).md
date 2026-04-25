# Family Office Intelligence — RAG Pipeline
**PolarityIQ Differentiator Assessment | Task 1**

---

## What This Is

A validated dataset of 53 real family office records and a queryable RAG pipeline built on top of it. The system lets you ask natural language questions about the dataset and get sourced, confidence-aware answers.

**Example queries that work:**
- "Which family offices are based in New York and focus on real estate?"
- "Show me HIGH confidence SFOs with AUM above $50 billion"
- "Which family offices have made acquisitions in healthcare?"
- "Who runs Mousse Partners and what do they invest in?"
- "Which European family offices focus on biotech?"

---

## Repository Structure

```
polarityiq-fo-rag/
│
├── data/
│   ├── family_offices_raw.xlsx          # Original 53 records with formatting
│   └── family_offices_rag_ready.csv     # Normalised, scored, RAG-ready
│
├── pipeline/
│   ├── normalize.py                     # Normalisation + AUM tier extraction
│   ├── validate.py                      # URL check + EDGAR lookup + completeness
│   ├── chunk_and_embed.py               # Prose paragraph generation + embedding
│   └── query_engine.py                  # Hybrid retrieval + synthesis
│
├── docs/
│   ├── methodology.md                   # How data was found, enriched, validated
│   ├── validation_chains.md             # 3 forensic record breakdowns
│   └── stack_decisions.md              # Every technical decision explained
│
├── app.py                               # Streamlit UI
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your OpenAI API key

```bash
export OPENAI_API_KEY=your_key_here
```

### 3. Run the data pipeline

```bash
# Step 1: Normalise
python pipeline/normalize.py

# Step 2: Validate
python pipeline/validate.py

# Step 3: Chunk and embed into ChromaDB
python pipeline/chunk_and_embed.py
```

### 4. Launch the UI

```bash
streamlit run app.py
```

---

## Requirements

```
pandas
openpyxl
chromadb
sentence-transformers
openai
streamlit
requests
```

---

## Dataset Overview

**53 records** across three confidence tiers:

| Confidence | Count | What it means |
|---|---|---|
| HIGH | 16 | 2+ independent sources confirmed each field. Fully reproducible validation path. |
| MEDIUM | 18 | 1 confirmed source + 1 inferred. Entity real, some fields estimated. |
| LOW | 19 | Single directory source (Axial). Deal history confirms activity. Principal/AUM unknown. |

**Validation results (validate.py):**
| Check | Result |
|---|---|
| Total records | 53 |
| LinkedIn URLs checked | 8 (1s delay each) |
| LinkedIn broken | 0 |
| Needs enrichment (score < 0.5) | 24 — expected, these are Axial-sourced records missing principal/AUM |
| Confidence mismatch | 0 |
| Passed all checks | 29 |

**Geographic breakdown:**
- USA: 38 records
- Europe: 9 records (UK, Germany, Spain, Monaco, Denmark)
- Asia/Middle East: 4 records (UAE, Indonesia)
- Canada: 2 records

**FO type breakdown:**
- Single Family Office (SFO): 46
- Multi-Family Office (MFO): 7

**AUM coverage:**
- $100B+ entities: 6
- $10B-$100B entities: 13
- $1B-$10B entities: 3
- Undisclosed: 31

---

## Data Sources

| Source | Records | How Used |
|---|---|---|
| Eagle Private (Jan 2026 report) | 20 | Primary source for top global SFOs |
| Axial.net directory | 30 | Mid-market US family offices with deal history |
| SEC EDGAR / 13F | 2 | Soros (CRD 106706), Cascade Investment |
| Crunchbase | Supporting | Investment signal verification |
| Bloomberg / Forbes | Supporting | AUM cross-validation for large SFOs |
| Annual reports | Supporting | KIRKBI, Ferrero Group |

---

## RAG Architecture

```
User Query
    ↓
Query Parser — extract structured filters (city, AUM tier, confidence, FO type)
    ↓
ChromaDB Metadata Filter — pre-filter by extracted structured fields
    ↓
Semantic Search — embedding similarity on filtered record set
    ↓
Top-K Retrieval — prose paragraph chunks returned
    ↓
GPT-4o-mini Synthesis — answer generated with source citations
    ↓
Response with sources + confidence levels
```

**Key design decision:** Two-stage retrieval (metadata filter → semantic search) was required after discovering that pure semantic search fails on numeric AUM comparisons. See `docs/stack_decisions.md` for full explanation.

---

## Known Limitations

1. **AUM figures are estimates** — family offices rarely disclose exact AUM. Treat all figures as indicative ranges.
2. **Contact data is thin** — emails are almost never publicly available for family offices. LinkedIn URLs included where confirmed.
3. **LOW confidence records have no named principals** — the Axial-sourced mid-market offices frequently do not disclose this publicly.
4. **The most secretive SFOs are not in this dataset** — private, non-digital family offices cannot be found through open-source intelligence.
5. **Signal freshness varies** — some signals are from 2025, some from 2023.

---

## What I Would Build Next

- **Automated signal refresh** — weekly news API job to update the Recent Signals field
- **Email discovery pass** — Hunter.io / Apollo integration for confirmed entities with known domains
- **SEC EDGAR monitoring** — automated scraping of new "family office" ADV registrations
- **Cross-encoder re-ranking** — third retrieval stage to improve precision on complex queries
- **Feedback loop** — thumbs up/down on query results to iteratively improve retrieval

---

## Validation Chains

Three records selected for full forensic documentation — a HIGH, MEDIUM, and LOW confidence record. Each documents the exact discovery source, extraction method, enrichment steps, what was and was not verified, and why the confidence tier was assigned.

See `docs/validation_chains.md`.

---

## Methodology

Full documentation of how the data was found, what failed, what worked, the enrichment process, confidence framework, and what I would do differently with more time.

See `docs/methodology.md`.
