"""Retrieve relevant family-office rows; optionally summarize with OpenAI."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import chromadb
import chromadb.errors
from chromadb.utils import embedding_functions
from openai import OpenAI

from .config import CHROMA_DIR, COLLECTION_NAME, DEFAULT_CHAT_MODEL, EMBEDDING_MODEL
from .documents import metadata_to_citation
from .query_engine import build_chroma_where_clause, hybrid_query_collection


@dataclass
class RetrievedChunk:
    document: str
    metadata: dict
    distance: float | None


def _embedding_fn():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
    )


def _get_or_build_collection():
    """
    Return the Chroma collection, ingesting from the workbook if missing or empty.

    Streamlit Cloud (and fresh clones) have no ``chroma_db/`` checkout because it
    is gitignored; this path creates it on first use.
    """
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = _embedding_fn()
    need_ingest = False
    try:
        col = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
        if col.count() == 0:
            need_ingest = True
    except chromadb.errors.NotFoundError:
        need_ingest = True

    if need_ingest:
        from .ingest import ingest

        ingest(reset=True)
        col = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
    return col


def ensure_chroma_populated() -> None:
    """Public hook for Streamlit to warm the index on startup (see streamlit_app)."""
    _get_or_build_collection()


def _collection():
    return _get_or_build_collection()


def retrieve(
    query: str,
    k: int = 6,
    extra_where: dict[str, Any] | None = None,
) -> list[RetrievedChunk]:
    col = _collection()
    # --- Two-stage hybrid retrieval (see src/query_engine.py) ---
    parsed = build_chroma_where_clause(query)
    n_results = int(k) if k is not None else 6
    res = hybrid_query_collection(
        col,
        query,
        n_results=n_results,
        parsed=parsed,
        extra_where=extra_where,
    )
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    out: list[RetrievedChunk] = []
    for doc, meta, dist in zip(docs, metas, dists):
        meta_d: dict[str, Any] = {}
        if isinstance(meta, dict):
            meta_d = dict(meta)
        dist_f: float | None = None
        if dist is not None:
            try:
                dist_f = float(dist)
            except (TypeError, ValueError):
                dist_f = None
        out.append(
            RetrievedChunk(
                document=str(doc),
                metadata=meta_d,
                distance=dist_f,
            )
        )
    return out


def format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for i, ch in enumerate(chunks, start=1):
        cite = metadata_to_citation(ch.metadata)
        blocks.append(f"### Record {i}\nCitation: {cite}\n{ch.document}\n")
    return "\n".join(blocks)


def answer_with_openai(question: str, chunks: list[RetrievedChunk]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = os.getenv("OPENAI_CHAT_MODEL", DEFAULT_CHAT_MODEL).strip() or DEFAULT_CHAT_MODEL
    context = format_context(chunks)
    client = OpenAI(api_key=api_key)

    system = (
        "You answer questions using ONLY the provided context about family offices. "
        "If the context does not contain enough information, say what is missing. "
        "When you state facts, tie them to a family office name from the context. "
        "End with a short 'Sources' line listing Primary/Secondary URLs from the context when present."
    )
    user = f"Question:\n{question}\n\nContext:\n{context}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def extractive_fallback(question: str, chunks: list[RetrievedChunk]) -> str:
    """No API key: return ranked excerpts so the demo still returns real rows."""
    if not chunks:
        return "No matching records found in the vector index. Run ingest first."
    lines = [
        "_OpenAI key not set — showing top retrieved rows (still grounded in your dataset)._",
        "",
        f"**Your question:** {question}",
        "",
    ]
    for i, ch in enumerate(chunks, start=1):
        lines.append(f"#### Match {i} (distance: {ch.distance})")
        lines.append(f"**{ch.metadata.get('fo_name', 'Unknown')}** — {metadata_to_citation(ch.metadata)}")
        lines.append("")
        lines.append(ch.document)
        lines.append("")
    return "\n".join(lines)
