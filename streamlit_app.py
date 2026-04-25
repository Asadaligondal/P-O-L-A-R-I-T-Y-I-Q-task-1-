"""
Family office RAG demo: queries your Excel-backed Chroma index.

Run from repo root:
  pip install -r requirements.txt
  python -m src.ingest
  streamlit run streamlit_app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Ensure repo root is importable when launched via `streamlit run`.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest import ingest  # noqa: E402
from src.rag_engine import answer_with_openai, extractive_fallback, retrieve  # noqa: E402


st.set_page_config(page_title="Family Office RAG", layout="wide")
st.title("Family office dataset — RAG query")

with st.sidebar:
    st.markdown("### Index")
    if st.button("Re-ingest from Excel"):
        with st.spinner("Ingesting…"):
            n = ingest(reset=True)
        st.success(f"Ingested {n} rows.")
    st.caption("Uses `family_office_dataset_50_records.xlsx` in the repo root only.")
    k = st.slider("Top K retrieval", min_value=3, max_value=12, value=6)
    st.markdown("### Model")
    has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    st.write("OpenAI key:", "set" if has_key else "not set (extractive answers)")

question = st.text_input(
    "Ask a question about the family offices in your spreadsheet",
    placeholder="Example: Which offices focus on venture capital in the United States?",
)

if st.button("Run query", type="primary") and question.strip():
    with st.spinner("Retrieving…"):
        chunks = retrieve(question.strip(), k=k)
    with st.spinner("Generating answer…"):
        try:
            if has_key:
                answer = answer_with_openai(question.strip(), chunks)
            else:
                answer = extractive_fallback(question.strip(), chunks)
        except Exception as e:
            answer = f"**Error:** {e}\n\nShowing extractive fallback."
            answer += "\n\n" + extractive_fallback(question.strip(), chunks)

    st.markdown("### Answer")
    st.markdown(answer)

    with st.expander("Retrieved context (verbatim)"):
        for i, ch in enumerate(chunks, start=1):
            st.markdown(f"**Chunk {i}** — `{ch.metadata.get('fo_name', '')}`")
            st.text(ch.document)

elif question.strip():
    st.caption('Press "Run query" to search.')
