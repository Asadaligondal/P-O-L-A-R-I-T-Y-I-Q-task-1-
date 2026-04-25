# Stack Decisions & RAG Architecture
**PolarityIQ Differentiator Assessment | Task 1**

---

## Overview

This document explains every technical decision made in building the RAG pipeline — what I chose, what I considered, why I made each call, and what I would change with more time or resources.

---

## Data Pipeline Stack

### Language: Python 3.11

No decision to justify here. Python is the standard for data pipelines and ML tooling. The relevant libraries all have Python-first support.

### Spreadsheet I/O: openpyxl + pandas

- **openpyxl** for writing formatted Excel output (the deliverable dataset)
- **pandas** for reading and manipulating records in the pipeline

Both are standard. The interesting decision was keeping AUM as a text field in the source Excel while extracting a parallel numeric tier for the vector store metadata. This preserves the honest uncertainty ("$90-100B") in the human-readable file while enabling structured filtering in the RAG layer.

### Normalisation Script (`normalize.py`)

Handles:
- Stripping inconsistent whitespace and encoding artifacts
- Standardising country names (USA vs United States vs US → USA)
- Standardising FO type (SFO / MFO / Undisclosed only — no freeform variants)
- Extracting AUM numeric tier from text ranges:
  - "$200B+" → tier: "200B+"
  - "$90-100B" → tier: "50B-200B"  
  - "$1B+" → tier: "1B-50B"
  - "Undisclosed" → tier: "unknown"
- Flagging completeness score (fields populated / total fields)

The AUM tier extraction is the most important normalisation step. Without it, any numeric filter query ("AUM above $X") fails entirely because vector embeddings cannot do numeric comparison. The tier approach is a pragmatic fix — not perfect, but functional.

### Validation Script (`validate.py`)

Runs three checks:

**Check 1 — URL resolution:** For every LinkedIn URL that is not "Undisclosed", sends a HEAD request. If the URL returns a 404 or redirect to LinkedIn's login wall, the record is flagged. This catches broken or guessed URLs.

**Check 2 — SEC EDGAR lookup:** For HIGH-confidence records, queries the EDGAR full-text search API for the entity name. If the entity name returns zero results on EDGAR, a warning is logged. (Note: not finding a result does not mean the record is wrong — most SFOs are exempt from registration — but it is a data point.)

**Check 3 — Completeness threshold:** Records with completeness score below 40% (fewer than ~8/19 fields populated) are flagged for enrichment review.

Output: `validation_report.json` — a machine-readable record of every check, pass/fail, and flag with reason.

---

## RAG Pipeline Stack

### Vector Store: ChromaDB (local, in-process)

**What I considered:**
- Pinecone (hosted, managed, production-grade)
- Weaviate (self-hosted, more features)
- ChromaDB (local, zero ops, open source)
- FAISS (ultra-fast, but no metadata filtering built in)

**Why ChromaDB:**
For a 50-record dataset the performance difference between any of these is irrelevant. ChromaDB runs in-process (no server to spin up), supports metadata filtering natively, and the setup is 3 lines of Python. The demo works within seconds of running the script.

The honest trade-off: ChromaDB does not scale to millions of records without significant rework. For a production family office intelligence product you would want Pinecone or Weaviate. For this assessment, ChromaDB is the right call — it lets me focus on retrieval logic rather than infrastructure.

### Embedding Model: sentence-transformers/all-MiniLM-L6-v2

**What I considered:**
- OpenAI text-embedding-ada-002 (hosted, paid, high quality)
- sentence-transformers/all-MiniLM-L6-v2 (local, free, fast, 384 dimensions)
- sentence-transformers/all-mpnet-base-v2 (local, free, better quality, 768 dimensions, slower)

**Why all-MiniLM-L6-v2:**
Runs locally with no API cost. For a 50-record dataset the quality difference between this and ada-002 is small in practice. The model is fast enough that re-embedding the entire dataset takes under 5 seconds, which matters for iteration speed during development.

The honest trade-off: for a production system with thousands of records and complex semantic queries, ada-002 or a domain-fine-tuned model would perform meaningfully better. Investment/finance vocabulary is not well-represented in a general-purpose model. A fine-tuned model on financial text (e.g., FinBERT derivatives) would improve retrieval accuracy on queries about investment mandates, asset classes, and deal structures.

### Chunking Strategy: One Record = One Prose Paragraph

This was the most consequential design decision in the pipeline.

**What I tried first (and abandoned):**
Embedding raw CSV rows as strings — `"fo_name: Mousse Partners | fo_type: SFO | hq_city: New York..."`. This produces poor embeddings because the string is structured data masquerading as text. The embedding captures field names and pipe characters as meaningful tokens.

**What I implemented:**
Each record is converted to a natural-language prose paragraph before embedding:

```
"Mousse Partners is a Single Family Office headquartered in New York, USA. 
It is managed by Charles Heilbronn (Managing Partner) and serves the Wertheimer 
family, owners of Chanel. Estimated AUM is $90-100B. The firm focuses on 
multi-asset investments including private equity, venture capital, and brand-adjacent 
assets, with a global geographic mandate. Recent activity includes leading the 2025 
recapitalisation of Rockefeller Capital Management and backing Brightside Health, 
Brandtech Group, and Thirty Madison. Primary source: Eagle Private 2026. 
Confidence: HIGH."
```

**Why this works better:**
Semantic search finds records based on meaning. "Who manages wealth from luxury brands" should return Mousse Partners. A prose paragraph that says "Wertheimer family, owners of Chanel" will embed that relationship in a way that a raw field value "Wertheimer family | Chanel" will not.

**The trade-off:**
Prose paragraphs are harder to update systematically than structured fields. If a field changes, you have to regenerate the paragraph. This is manageable at 50 records and worth the retrieval quality improvement.

### Retrieval Approach: Hybrid (Metadata Filter → Semantic Search)

**The problem I identified and had to fix:**

The initial implementation used pure semantic search on all records simultaneously. This caused a visible failure: a query for "FOs with AUM above $100M" returned only 4 results, missing Walton ($200B+), Bezos ($200B+), Mousse ($90-100B), and Pontegadea ($115B).

**Why it failed:** Embedding similarity cannot do numeric comparison. "$200B+" and "$90-100B" embedded as text have no mathematical relationship to "> $100M". The vector similarity score between the query and those records was lower than records that happened to use the word "billion" more prominently.

**The fix — two-stage retrieval:**

Stage 1 — Metadata filter (structured):
```python
# Extract structured intent from query
# "FOs with AUM above $100M" → {aum_tier: ["50B-200B", "200B+"]}
# "New York family offices" → {hq_city: "New York"}
# Apply as ChromaDB where clause BEFORE vector search
```

Stage 2 — Semantic search on filtered set:
```python
# Run embedding similarity only on records that passed the metadata filter
# Return top-k by semantic score from the filtered subset
```

**Query understanding layer:**
Before hitting the vector store, a lightweight query parser extracts structured filters from natural language. The parser handles:
- City/country mentions → `hq_city` or `hq_country` filter
- AUM-related language → `aum_tier` filter
- Confidence-related language → `confidence_score` filter
- FO type → `fo_type` filter
- Everything else → pure semantic on full set

This is not a full NLP pipeline — it is pattern matching on common query structures. Good enough for a demo, would need to be replaced with a proper intent classifier for production.

### LLM for Answer Synthesis: OpenAI GPT-4o-mini

The retrieved chunks are passed as context to GPT-4o-mini with a system prompt that instructs it to:
- Answer only from the provided context
- Cite the primary source for each claim
- State explicitly when a field is "Undisclosed" rather than inventing a value
- Note confidence levels when relevant

The "cite your sources" instruction is critical for a dataset like this. A RAG system that answers "The principal is X" without noting whether X came from SEC filings or an Axial self-report is misleading.

---

**Results ordering:** Results are ordered by semantic similarity score, not by AUM magnitude. A query for "AUM above $100M" may return Fingerboard ($12-19B) ranked above Walton ($200B+) if Fingerboard's prose chunk is semantically closer to the query. This is a known limitation — a proper fix would add a post-retrieval re-ranker that weights by AUM tier when the query is AUM-focused.

## What Works

- Prose paragraph chunking significantly improves semantic retrieval over raw field strings
- Metadata pre-filtering fixes the numeric comparison failure
- ChromaDB setup is fast and reliable for demo purposes
- Source citation in answers correctly attributes data back to original sources

---

## What Does Not Work Well

**AUM tier extraction is crude.** The regex-based text-to-tier conversion handles common formats but will miss edge cases. A proper solution would store AUM as both text (human-readable) and numeric midpoint (for filtering) at data entry time, not as a post-processing step.

**Query parser misses complex filters.** "Show me European family offices focused on biotech with HIGH confidence" requires correctly extracting three simultaneous filters. The current parser handles two. The third is dropped.

**No re-ranking.** The current pipeline returns top-k by embedding similarity from the filtered set. A production system would add a cross-encoder re-ranker as a third stage to improve precision on the final result set.

**No feedback loop.** There is no mechanism to learn from which answers users found useful. In production this would be the primary driver of retrieval improvement over time.

---

## What I Would Do Differently

**Use a finance-domain embedding model.** General-purpose sentence transformers do not understand that "buyout" and "acquisition" are synonyms in PE context, or that "dry powder" refers to uninvested capital. A domain-adapted model would improve retrieval accuracy meaningfully.

**Store AUM as numeric at source.** The text-to-tier hack is fragile. The right approach is to capture a numeric midpoint at data entry and use range queries directly.

**Add a Streamlit query history with thumbs-up/down.** Even simple binary feedback on results would let you iteratively improve the retrieval logic over weeks.

**Replace pattern-matching query parser with a small LLM call.** Use a fast, cheap LLM call to extract structured filters from the natural language query before hitting the vector store. More robust than regex, handles complex multi-filter queries.
