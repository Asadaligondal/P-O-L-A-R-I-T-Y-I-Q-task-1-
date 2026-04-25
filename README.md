# Task 1 — Family office dataset + RAG

This repository contains a **RAG pipeline** over your workbook [`family_office_dataset_50_records.xlsx`](family_office_dataset_50_records.xlsx) (sheet `Family Office Dataset`). The FO-MAX sample file is **not** read or imported anywhere in code; it was only used informally to think about column groupings. All runtime data comes from your root Excel file.

## Prerequisites

- Python 3.11+ recommended
- (Optional) `OPENAI_API_KEY` for chat-style answers; without it, the UI returns **ranked verbatim excerpts** from retrieved rows (still fully grounded in your sheet).

## Quick start

```bash
cd "c:\Users\victus\Downloads\Task 1"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.ingest
streamlit run streamlit_app.py
```

Copy `.env.example` to `.env` and add your key if you want OpenAI summarization.

## Stack choices

| Piece | Choice | Why |
|-------|--------|-----|
| Data | Pandas + openpyxl | Native Excel IO for your deliverable |
| Vector DB | Chroma persistent on disk | Simple local demo, no external DB |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` via Chroma’s embedding helper | No API key required; good enough for 50-ish structured rows |
| UI | Streamlit | Fast demo deploy (Streamlit Community Cloud, etc.) |
| Optional LLM | OpenAI `gpt-4o-mini` (override with `OPENAI_CHAT_MODEL`) | Cheap, strong instruction-following for “answer only from context” |

## Chunking strategy

- **One family office = one chunk.** Each row is rendered as labeled lines (`Family office name: …`, `Primary validation source: …`, etc.) in [`src/documents.py`](src/documents.py).
- This avoids splitting a single office across chunks and keeps sources co-located with the fields they support.

## Retrieval approach

- Embedding the user question with the same model as ingestion.
- **Top-K** similarity search (default K=6 in the UI).
- Optional **OpenAI** step: system prompt restricts answers to provided context and asks for source URLs when present.
- **No-key mode**: no generative model; the app shows the top matching rows verbatim (transparent and still “real results” from your dataset).

## What works / what does not

- **Works:** Faithful retrieval over ~50 wide rows; citations tied to `Primary Source` / `Secondary Source` fields in the sheet; trivial re-ingest when you edit the Excel file.
- **Does not:** Synonym-heavy questions that never overlap your text may return weak matches—there is no keyword BM25 hybrid in this minimal build.
- **Improve:** Add hybrid BM25 + vector, query expansion, and/or metadata filters (country, FO type) as UI facets; cache embeddings if the sheet grows.

## Dataset note

The ingestion sheet currently contains **53** populated rows (0-based index after dropping blank rows). Adjust the workbook if you need exactly 50 for submission; the pipeline ingests whatever non-empty rows are present.

## License / assessment

Built for the Polarity IQ stage-1 task. Dataset content is yours per the task disclaimer.
