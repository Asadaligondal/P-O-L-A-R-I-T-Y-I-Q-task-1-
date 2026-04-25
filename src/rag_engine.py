"""Retrieve relevant family-office rows; optionally summarize with OpenAI."""
from __future__ import annotations

import os
from dataclasses import dataclass

import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

from .config import CHROMA_DIR, COLLECTION_NAME, DEFAULT_CHAT_MODEL, EMBEDDING_MODEL
from .documents import metadata_to_citation


@dataclass
class RetrievedChunk:
    document: str
    metadata: dict
    distance: float | None


def _collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
    )
    return client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)


def retrieve(query: str, k: int = 6) -> list[RetrievedChunk]:
    col = _collection()
    res = col.query(query_texts=[query], n_results=k, include=["documents", "metadatas", "distances"])
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    out: list[RetrievedChunk] = []
    for doc, meta, dist in zip(docs, metas, dists):
        out.append(
            RetrievedChunk(
                document=str(doc),
                metadata=dict(meta) if meta else {},
                distance=float(dist) if dist is not None else None,
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
