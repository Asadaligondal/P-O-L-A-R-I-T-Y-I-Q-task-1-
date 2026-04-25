#!/usr/bin/env python3
"""
Script 2 — Turn normalised CSV rows into prose chunks, embed, store in Chroma.

Reads:  family_offices_normalised.csv (from normalize.py)
Uses:   sentence-transformers all-MiniLM-L6-v2 (via Chroma embedding function)
Stores: ./chroma_db_csv  collection ``family_offices_normalised``

Run from repo root:
  python chunk_and_embed.py
  python chunk_and_embed.py --input family_offices_normalised.csv --append
"""
from __future__ import annotations

import argparse
from pathlib import Path

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_DIR = Path("chroma_db_csv")
COLLECTION_NAME = "family_offices_normalised"


def _clean(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def is_missing(v: object) -> bool:
    s = _clean(v).lower()
    return not s or s in {"undisclosed", "unknown", "n/a", "na", "-"}


def row_to_paragraph(row: pd.Series) -> str:
    """Prose template aligned with the prompt."""
    name = _clean(row.get("fo_name", ""))
    fo_type = _clean(row.get("fo_type", ""))
    city = _clean(row.get("hq_city", ""))
    country = _clean(row.get("hq_country", ""))
    hq = ""
    if city and country:
        hq = f"headquartered in {city}, {country}"
    elif country:
        hq = f"headquartered in {country}"
    elif city:
        hq = f"headquartered in {city}"

    if fo_type and hq:
        lead = f"{name} is a {fo_type} {hq}."
    elif fo_type:
        lead = f"{name} is a {fo_type}."
    elif hq:
        lead = f"{name} is a family office {hq}."
    else:
        lead = f"{name} is a family office."

    parts: list[str] = [lead]

    pname = _clean(row.get("principal_name", ""))
    ptitle = _clean(row.get("principal_title", ""))
    if not is_missing(pname):
        role = f" ({ptitle})" if not is_missing(ptitle) else ""
        parts.append(f"It is managed by {pname}{role}.")

    aum = _clean(row.get("aum_usd_est", ""))
    if not is_missing(aum):
        parts.append(f"Estimated AUM is {aum}.")

    focus = _clean(row.get("investment_focus", ""))
    mandate = _clean(row.get("geographic_mandate", ""))
    if not is_missing(focus):
        if not is_missing(mandate):
            parts.append(f"The firm focuses on {focus} with a {mandate} geographic mandate.")
        else:
            parts.append(f"The firm focuses on {focus}.")

    signals = _clean(row.get("recent_signals", ""))
    if not is_missing(signals):
        parts.append(signals.rstrip(".") + ".")

    ps = _clean(row.get("primary_source", ""))
    if not is_missing(ps):
        parts.append(f"Primary source: {ps}.")

    conf = _clean(row.get("confidence_score", ""))
    if not is_missing(conf):
        parts.append(f"Confidence: {conf}.")

    return " ".join(parts)


def row_metadata(row: pd.Series, row_index: int) -> dict[str, str]:
    """Metadata keys requested in the prompt (Chroma-friendly strings)."""
    cs = row.get("completeness_score", "")
    if isinstance(cs, float) and pd.isna(cs):
        cs_s = ""
    else:
        cs_s = str(cs)
    return {
        "fo_name": _clean(row.get("fo_name", ""))[:500],
        "fo_type": _clean(row.get("fo_type", ""))[:100],
        "hq_city": _clean(row.get("hq_city", ""))[:200],
        "hq_country": _clean(row.get("hq_country", ""))[:200],
        "aum_tier": _clean(row.get("aum_tier", ""))[:50],
        "confidence_score": _clean(row.get("confidence_score", ""))[:100],
        "completeness_score": cs_s[:50],
        "row_index": str(row_index),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Chunk, embed, and store normalised FO CSV in Chroma.")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path("family_offices_normalised.csv"),
        help="Normalised CSV from normalize.py",
    )
    ap.add_argument(
        "--append",
        action="store_true",
        help="If set, do not delete the collection first (may fail if IDs already exist).",
    )
    args = ap.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Input not found: {args.input.resolve()}. Run normalize.py first.")

    df = pd.read_csv(args.input)
    df = df.dropna(how="all")

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for i, (_, row) in enumerate(df.iterrows()):
        text = row_to_paragraph(row)
        if not text.strip():
            continue
        documents.append(text)
        metadatas.append(row_metadata(row, i))
        ids.append(f"fo_csv_{i}")

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR.resolve()))
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    if not args.append:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    coll = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=emb)
    coll.add(documents=documents, metadatas=metadatas, ids=ids)
    print(f"Embedded {len(documents)} records into {CHROMA_DIR.resolve()} / collection={COLLECTION_NAME!r}.")


if __name__ == "__main__":
    main()
