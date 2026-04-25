# Task 1 — Family office dataset + RAG

This repository contains a **data-quality pipeline** and **RAG stack** over your workbook [`family_office_dataset_50_records.xlsx`](family_office_dataset_50_records.xlsx) (sheet `Family Office Dataset`). The FO-MAX sample file is **not** read or imported anywhere in code.

**Ingestion prefers the processed artifact** [`artifacts/dataset_for_rag.xlsx`](artifacts/dataset_for_rag.xlsx) when it exists (so: run the pipeline first, or delete that file to ingest the raw workbook only).

## Prerequisites

- Python 3.11+ recommended
- Outbound HTTPS for automated validation (LinkedIn GET, SEC search POST, Google News RSS)
- (Optional) `OPENAI_API_KEY` for chat-style answers; without it, the UI returns **ranked verbatim excerpts** from retrieved rows.

## Quick start (end-to-end)

From the repo root (`Task 1`):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

**1 — Build the processed dataset + reports**

```powershell
# Fast (no external HTTP): normalization, completeness, enrichment queue, signal_age
python -m src.pipeline --skip-validation

# Full validation (slow: ~0.35s delay × row count per external round-trip batch; expect several minutes)
$env:SEC_USER_AGENT="YourName FamilyOfficeRAG/1.0 (you@example.com)"
python -m src.pipeline
```

**2 — Embed rows into Chroma**

```powershell
python -m src.ingest
```

**3 — Query UI**

```powershell
streamlit run streamlit_app.py
```

Copy [`.env.example`](.env.example) to `.env` and add `OPENAI_API_KEY` / `SEC_USER_AGENT` as needed.

---

## Data pipeline (recommended order: 3 → 2 → 6 → 1 → 4 → 5)

| Step | What it does | Code |
|------|----------------|------|
| **3** | Normalizes city/country/AUM text; flags possible geo mismatches; fuzzy near-duplicate **report** (no auto-deletes) | [`src/pipeline/normalize.py`](src/pipeline/normalize.py) |
| **2** | `Completeness Score` = filled ÷ 19 core columns (treats blank / “undisclosed” / n/a as empty) | [`src/pipeline/completeness.py`](src/pipeline/completeness.py) |
| **6** | Each row becomes a **single prose paragraph** for embedding (better retrieval than raw `field: value` lines) | [`src/pipeline/prose.py`](src/pipeline/prose.py) via [`src/documents.py`](src/documents.py) |
| **1** | Optional HTTP checks: LinkedIn URL reachability, SEC EDGAR search hit count, Google News RSS item count → `programmatic_confidence` | [`src/pipeline/validate_records.py`](src/pipeline/validate_records.py) |
| **4** | Writes `artifacts/enrichment_queue.csv` with **Google search URLs** for low-completeness / missing principal rows (**no LinkedIn scraping or login**) | [`src/pipeline/enrich_suggest.py`](src/pipeline/enrich_suggest.py) |
| **5** | `signal_age` bucket from years found in “Recent Signals / Activity” + “Last Validated” | [`src/pipeline/signal_freshness.py`](src/pipeline/signal_freshness.py) |

Orchestration + Excel artifact output: [`src/pipeline/run_pipeline.py`](src/pipeline/run_pipeline.py) (CLI: `python -m src.pipeline` or `python -m src.pipeline.run_pipeline`).

---

## How to verify each step

| Step | How to verify |
|------|----------------|
| **3 Normalize / dedup** | Open [`artifacts/dataset_for_rag.xlsx`](artifacts/dataset_for_rag.xlsx) and check columns `HQ City Normalized`, `HQ Country Normalized`, `AUM Normalized`, `_geo_mismatch_flag`. Open [`artifacts/dedup_report.csv`](artifacts/dedup_report.csv) — any row pairs listed are fuzzy name matches to review manually. |
| **2 Completeness** | In the same XLSX, column `Completeness Score` is between 0 and 1; `_completeness_filled` / `_completeness_total` show the count. Spot-check one sparse row. |
| **6 Prose chunks** | Run `python -m src.ingest`, then in Streamlit expand **Retrieved context** — text should read as a **paragraph**, not a bulleted field dump. |
| **1 Validation** | With **full** pipeline (no `--skip-validation`), inspect `linkedin_resolves`, `sec_edgar_hit_count`, `google_news_rss_item_count`, `programmatic_confidence`. Expect many LinkedIn rows as `no` if the site returns a login wall (still a useful automated signal). |
| **4 Enrichment queue** | Open [`artifacts/enrichment_queue.csv`](artifacts/enrichment_queue.csv); confirm suggested URLs open in a browser and match rows that need principals. |
| **5 Signal age** | Column `signal_age` in the artifact; values in `2025` / `2024` / `2023-or-older` / `unknown`. |
| **Pipeline summary** | [`artifacts/pipeline_summary.txt`](artifacts/pipeline_summary.txt) timestamps and row counts. |

---

## Stack choices

| Piece | Choice | Why |
|-------|--------|-----|
| Data | Pandas + openpyxl | Native Excel IO |
| Quality | rapidfuzz + requests | Dedup fuzz + polite HTTP |
| Vector DB | Chroma persistent on disk | Simple local demo |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | No API key |
| UI | Streamlit | Sidebar pipeline + query |
| Optional LLM | OpenAI `gpt-4o-mini` | Grounded answers when `OPENAI_API_KEY` is set |

## Chunking / retrieval

- **One family office = one chunk**, body = **prose paragraph** (step 6).
- Metadata includes `signal_age`, `completeness_score`, `programmatic_confidence` for transparency in the UI / future filtering.
- **Top-K** vector search (K configurable in Streamlit).

## What works / what does not

- **Works:** Normalization + completeness + prose retrieval; enrichment **suggestions** without scraping LinkedIn.
- **Does not:** LinkedIn “public” checks often hit auth walls (`linkedin_resolves=no`); SEC JSON shape may change (see `sec_check_note`); Google News RSS is a coarse signal, not exhaustive news coverage.
- **Improve:** Hybrid BM25 + vector; metadata filters (e.g. only `signal_age=2025`); SEC caching; optional SerpAPI for richer news if you add a key.

## Dataset note

The sheet currently has **53** populated rows. Trim in Excel if you need exactly **50** for submission.

## License / assessment

Built for the Polarity IQ stage-1 task. Dataset content is yours per the task disclaimer.
