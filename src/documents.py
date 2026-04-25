"""Turn spreadsheet rows into retrieval-friendly text + metadata."""
from __future__ import annotations

from typing import Any

import pandas as pd

# Order matters for readability in the chunk.
FIELD_LABELS: list[tuple[str, str]] = [
    ("FO Name", "Family office name"),
    ("FO Type (SFO/MFO)", "Office type"),
    ("HQ City", "Headquarters city"),
    ("HQ Country", "Headquarters country"),
    ("AUM Est. (USD)", "Estimated AUM (USD)"),
    ("Principal Name", "Principal / key contact name"),
    ("Principal Title", "Principal title"),
    ("Principal LinkedIn", "Principal LinkedIn URL"),
    ("Principal Email", "Principal email"),
    ("Investment Focus", "Investment focus"),
    ("Geographic Mandate", "Geographic mandate"),
    ("Check Size Est.", "Estimated check size"),
    ("Recent Signals / Activity", "Recent signals or activity"),
    ("Primary Source", "Primary validation source"),
    ("Secondary Source", "Secondary validation source"),
    ("Confidence Score", "Confidence score"),
    ("Confidence Reason", "Confidence rationale"),
    ("Last Validated", "Last validated date"),
    ("Notes / Caveats", "Notes and caveats"),
]


def _clean(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def row_to_text(row: pd.Series) -> str:
    lines: list[str] = []
    for col, label in FIELD_LABELS:
        val = _clean(row.get(col, ""))
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def row_metadata(row: pd.Series, row_index: int) -> dict[str, str]:
    """Small, filter-friendly metadata stored alongside embeddings."""
    name = _clean(row.get("FO Name", ""))
    return {
        "fo_name": name[:500],
        "fo_type": _clean(row.get("FO Type (SFO/MFO)", ""))[:200],
        "hq_country": _clean(row.get("HQ Country", ""))[:200],
        "primary_source": _clean(row.get("Primary Source", ""))[:2000],
        "secondary_source": _clean(row.get("Secondary Source", ""))[:2000],
        "confidence_score": _clean(row.get("Confidence Score", ""))[:100],
        "row_index": str(row_index),
    }


def dataframe_to_documents(df: pd.DataFrame) -> tuple[list[str], list[dict], list[str]]:
    texts: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    for idx, row in df.iterrows():
        text = row_to_text(row)
        if not text:
            continue
        texts.append(text)
        metadatas.append(row_metadata(row, int(idx)))
        ids.append(f"fo_{int(idx)}")
    return texts, metadatas, ids


def metadata_to_citation(meta: dict[str, str]) -> str:
    """Human-readable citation line for UI."""
    parts = [meta.get("fo_name", "Unknown FO")]
    ps = meta.get("primary_source", "")
    ss = meta.get("secondary_source", "")
    if ps:
        parts.append(f"Primary: {ps}")
    if ss:
        parts.append(f"Secondary: {ss}")
    return " | ".join(parts)
