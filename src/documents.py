"""Turn spreadsheet rows into retrieval-friendly text + metadata."""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.pipeline.prose import row_to_prose
from src.query_engine import infer_aum_tier_from_text


def _clean(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def row_to_text(row: pd.Series) -> str:
    """Dense prose paragraph for embeddings (recommended over field lists)."""
    return row_to_prose(row)


def _fo_type_bucket(row: pd.Series) -> str:
    """Normalize FO type for Chroma $eq filters (SFO / MFO)."""
    ft = _clean(row.get("FO Type (SFO/MFO)", "")).upper()
    if "MFO" in ft or "MULTI" in ft:
        return "MFO"
    if "SFO" in ft or "SINGLE" in ft:
        return "SFO"
    return (ft[:50] or "unknown").strip()


def row_metadata(row: pd.Series, row_index: int) -> dict[str, str]:
    """Small, filter-friendly metadata stored alongside embeddings."""
    name = _clean(row.get("FO Name", ""))
    aum_blob = " ".join(
        [
            _clean(row.get("AUM Normalized", "")),
            _clean(row.get("AUM Est. (USD)", "")),
        ]
    )
    conf = _clean(row.get("Confidence Score", "")).upper() or "unknown"
    meta = {
        "fo_name": name[:500],
        "fo_type": _fo_type_bucket(row)[:50],
        "hq_city": (_clean(row.get("HQ City Normalized", "")) or _clean(row.get("HQ City", "")))[:200],
        "hq_country": _clean(row.get("HQ Country Normalized", ""))[:200] or _clean(row.get("HQ Country", ""))[:200],
        "aum_tier": infer_aum_tier_from_text(aum_blob)[:50],
        "confidence_score": conf[:50],
        "primary_source": _clean(row.get("Primary Source", ""))[:2000],
        "secondary_source": _clean(row.get("Secondary Source", ""))[:2000],
        "row_index": str(row_index),
        "signal_age": _clean(row.get("signal_age", ""))[:50],
        "completeness_score": _clean(row.get("Completeness Score", ""))[:20],
        "programmatic_confidence": _clean(row.get("programmatic_confidence", ""))[:50],
    }
    return meta


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
