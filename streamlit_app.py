"""
Family office RAG demo: queries your Excel-backed Chroma index.

Run from repo root:
  pip install -r requirements.txt
  python -m src.ingest
  streamlit run streamlit_app.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Streamlit's import watcher calls hasattr(..., "__path__") on every sys.modules
# entry; HuggingFace ``transformers`` lazy-loads vision stacks that need
# ``torchvision``, which this app does not use — log noise only, not app errors.
logging.getLogger("streamlit.watcher.local_sources_watcher").setLevel(logging.ERROR)

from dotenv import load_dotenv

load_dotenv()

# Ensure repo root is importable when launched via `streamlit run`.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import (  # noqa: E402
    ARTIFACTS_DIR,
    CHROMA_DIR,
    DATA_ARTIFACT_XLSX,
    DATA_SHEET,
    resolved_dataset_path,
)
from src.ingest import ingest  # noqa: E402
from src.pipeline.run_pipeline import run_pipeline  # noqa: E402
from src.rag_engine import (  # noqa: E402
    RetrievedChunk,
    answer_with_openai,
    ensure_chroma_populated,
    extractive_fallback,
    retrieve,
)

EXAMPLE_QUERIES: list[tuple[str, str]] = [
    ("AUM > $100M", "Which family offices have AUM above $100M?"),
    ("SFO + USA", "Single family offices in the United States"),
    ("HIGH confidence", "Show offices with high confidence"),
    ("VC / tech", "Who focuses on venture capital or technology?"),
    ("Europe", "Family offices headquartered in Europe or the UK"),
]


def _apply_dark_theme() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stAppViewContainer"] { background-color: #0e1117; color: #e6edf3; }
          [data-testid="stHeader"] { background-color: #0e1117; }
          [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
          [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { color: #e6edf3; }
          .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            background-color: #21262d !important; color: #e6edf3 !important;
          }
          div[data-testid="stExpander"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=120, show_spinner=False)
def load_dataset_df() -> pd.DataFrame:
    path = resolved_dataset_path()
    if not path.is_file():
        return pd.DataFrame()
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=DATA_SHEET)
    return pd.read_csv(path)


def hq_country_series(df: pd.DataFrame) -> pd.Series:
    if "HQ Country Normalized" in df.columns:
        c = df["HQ Country Normalized"].fillna(df.get("HQ Country", ""))
    else:
        c = df.get("HQ Country", pd.Series(dtype=str))
    return c.fillna("").astype(str).str.strip()


def dataset_stats(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "total": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "top_countries": [],
        }
    col = "Confidence Score" if "Confidence Score" in df.columns else None
    if col:
        conf = df[col].astype(str).str.strip().str.upper()
        high = int((conf == "HIGH").sum())
        med = int((conf == "MEDIUM").sum())
        low = int((conf == "LOW").sum())
    else:
        high = med = low = 0
    hc = hq_country_series(df)
    vc = hc[hc != ""].value_counts().head(5)
    top = [(str(name), int(vc.loc[name])) for name in vc.index]
    return {"total": len(df), "high": high, "medium": med, "low": low, "top_countries": top}


def build_sidebar_where(fo: str, conf: str, country: str) -> dict[str, Any] | None:
    parts: list[dict[str, Any]] = []
    if fo and fo != "All":
        parts.append({"fo_type": {"$eq": fo}})
    if conf and conf != "All":
        parts.append({"confidence_score": {"$eq": conf}})
    if country and country != "All":
        parts.append({"hq_country": {"$eq": country}})
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


def confidence_distribution(chunks: list[RetrievedChunk]) -> tuple[int, int, int, int]:
    hi = mid = lo = other = 0
    for ch in chunks:
        v = str(ch.metadata.get("confidence_score", "") or "").strip().upper()
        if v == "HIGH":
            hi += 1
        elif v == "MEDIUM":
            mid += 1
        elif v == "LOW":
            lo += 1
        else:
            other += 1
    return hi, mid, lo, other


def render_pipeline_status() -> None:
    """Sidebar: last pipeline run text + which artifact columns / files exist."""
    with st.expander("Pipeline status", expanded=False):
        summary_path = ARTIFACTS_DIR / "pipeline_summary.txt"
        if summary_path.is_file():
            st.markdown("**Last run (`pipeline_summary.txt`)**")
            st.code(summary_path.read_text(encoding="utf-8").strip(), language=None)
        else:
            st.info("No `artifacts/pipeline_summary.txt` yet — run **Run quality pipeline** above once.")

        st.markdown("**Step checks (artifact workbook)**")
        if not DATA_ARTIFACT_XLSX.is_file():
            st.warning("`artifacts/dataset_for_rag.xlsx` missing — ingest falls back to the raw workbook.")
        else:
            try:
                header = pd.read_excel(DATA_ARTIFACT_XLSX, sheet_name=DATA_SHEET, nrows=0)
                colset = set(header.columns.astype(str))
            except Exception as e:
                st.error(f"Could not read artifact header: {e}")
                colset = set()

            def has_all(names: list[str]) -> bool:
                return all(n in colset for n in names)

            rows = [
                ("3 · Normalize", ["HQ City Normalized", "HQ Country Normalized", "AUM Normalized"]),
                ("2 · Completeness", ["Completeness Score", "_completeness_filled"]),
                ("5 · Signal age", ["signal_age"]),
                ("1 · Validation", ["programmatic_confidence", "linkedin_resolves", "sec_edgar_hit_count"]),
            ]
            for label, keys in rows:
                ok = has_all(keys)
                st.markdown(f"{'[x]' if ok else '[ ]'} **{label}** — column set {'present' if ok else 'missing'}")

        st.markdown("**Report files**")
        dedup = ARTIFACTS_DIR / "dedup_report.csv"
        enrich = ARTIFACTS_DIR / "enrichment_queue.csv"
        st.markdown(
            f"- dedup_report.csv: **{'yes' if dedup.is_file() else 'no'}**"
            + (f" ({dedup.stat().st_size} bytes)" if dedup.is_file() else "")
        )
        st.markdown(
            f"- enrichment_queue.csv: **{'yes' if enrich.is_file() else 'no'}**"
            + (f" ({enrich.stat().st_size} bytes)" if enrich.is_file() else "")
        )

        st.markdown("**RAG index (Chroma)**")
        chroma_ok = CHROMA_DIR.is_dir() and any(CHROMA_DIR.iterdir())
        st.markdown(f"- `chroma_db` populated: **{'yes' if chroma_ok else 'no'}**")
        if not chroma_ok:
            st.caption("Run: `python -m src.ingest`")

        st.markdown("**Ingest text shape (step 6 · prose)**")
        st.caption("Chunks are built as one paragraph per row at ingest. Open **Retrieved context** after a query to inspect.")


# --- Page -------------------------------------------------------------------
st.set_page_config(page_title="Family Office RAG", layout="wide", initial_sidebar_state="expanded")
# Streamlit Cloud exposes secrets via st.secrets, not always in os.environ before
# other modules read OPENAI_API_KEY (e.g. rag_engine, OpenAI client).
try:
    _sk = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
    if _sk:
        os.environ.setdefault("OPENAI_API_KEY", _sk)
except Exception:
    pass
_apply_dark_theme()
st.title("Family office dataset — RAG query")


@st.cache_resource(
    show_spinner="Building vector index (first open only; downloads embedding model)…",
)
def _bootstrap_chroma_index() -> None:
    """Chroma lives in gitignored ``chroma_db/`` — create it on Streamlit Cloud / fresh clone."""
    ensure_chroma_populated()


_bootstrap_chroma_index()

df = load_dataset_df()
stats = dataset_stats(df)
hc_series = hq_country_series(df) if not df.empty else pd.Series(dtype=str)
country_options = ["All"] + sorted({c for c in hc_series.tolist() if c})

st.session_state.setdefault("rag_query", "")

st.markdown("**Example queries**")
ex_cols = st.columns(min(5, len(EXAMPLE_QUERIES)))
for i, (label, full_q) in enumerate(EXAMPLE_QUERIES):
    with ex_cols[i % len(ex_cols)]:
        if st.button(label, key=f"ex_{i}"):
            st.session_state.rag_query = full_q
            st.rerun()

question = st.text_input(
    "Ask a question about the family offices in your spreadsheet",
    key="rag_query",
    placeholder="Example: Which offices focus on venture capital in the United States?",
)

with st.sidebar:
    st.markdown("### Dataset")
    if stats["total"] == 0:
        st.warning("Could not load dataset for stats (check workbook path).")
    else:
        st.metric("Total records", stats["total"])
        st.markdown("**Confidence (sheet)**")
        st.caption(f"HIGH: **{stats['high']}** · MEDIUM: **{stats['medium']}** · LOW: **{stats['low']}**")
        st.markdown("**Top countries**")
        for name, cnt in stats["top_countries"]:
            st.caption(f"{name}: **{cnt}**")

    st.markdown("### Filters")
    st.caption("Applied as Chroma metadata filters before semantic search.")
    fo_f = st.selectbox("FO type", ["All", "SFO", "MFO"], index=0, key="f_fo")
    conf_f = st.selectbox("Confidence", ["All", "HIGH", "MEDIUM", "LOW"], index=0, key="f_conf")
    country_f = st.selectbox("Country", country_options, index=0, key="f_country")
    sidebar_where = build_sidebar_where(fo_f, conf_f, country_f)

    st.markdown("### Data pipeline")
    skip_net = st.checkbox("Skip network validation (faster)", value=True)
    if st.button("Run quality pipeline (normalize → score → validate → …)"):
        with st.spinner("Running pipeline (may take minutes if validation is on)…"):
            out = run_pipeline(skip_validation=skip_net)
        st.success(f"Wrote {out.name}. See artifacts/ for CSV reports.")
        st.cache_data.clear()
    st.markdown("### Index")
    if st.button("Re-ingest from Excel"):
        with st.spinner("Ingesting…"):
            n = ingest(reset=True)
        st.success(f"Ingested {n} rows.")
        st.cache_data.clear()
    st.caption(f"Active file: `{resolved_dataset_path().name}` (artifact preferred if present).")
    render_pipeline_status()
    st.slider("Top K retrieval", min_value=3, max_value=12, value=6, key="rag_k")
    st.markdown("### Model")
    has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    st.write("OpenAI key:", "set" if has_key else "not set (extractive answers)")

if st.button("Run query", type="primary") and question.strip():
    k_run = int(st.session_state.get("rag_k", 6))
    sidebar_where_run = build_sidebar_where(
        str(st.session_state.get("f_fo", "All")),
        str(st.session_state.get("f_conf", "All")),
        str(st.session_state.get("f_country", "All")),
    )
    with st.spinner("Retrieving…"):
        chunks = retrieve(question.strip(), k=k_run, extra_where=sidebar_where_run)
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

    hi, mid, lo, other = confidence_distribution(chunks)
    n = len(chunks)
    foot = (
        f"Answer based on **{n}** retrieved record(s). "
        f"Confidence distribution: **{hi}** HIGH, **{mid}** MEDIUM, **{lo}** LOW."
    )
    if other:
        foot += f" Other / unknown: **{other}**."
    st.caption(foot)

    with st.expander("Retrieved context (verbatim)", expanded=False):
        for i, ch in enumerate(chunks, start=1):
            rec = ch.metadata.get("fo_name", "Unknown record")
            conf = ch.metadata.get("confidence_score", "") or "—"
            dist = ch.distance
            st.markdown(f"**Chunk {i}** — **{rec}** · confidence: `{conf}` · distance: `{dist}`")
            st.text(ch.document)
            st.divider()

elif question.strip():
    st.caption('Press "Run query" to search.')
