"""
Step 3: Normalization + near-duplicate report.

Does not drop rows automatically; writes a report for manual review.
"""
from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from .text_utils import clean_str, normalize_whitespace

# Display / retrieval: expand common abbreviations in normalized copy used for RAG.
US_CITY_ALIASES: dict[str, str] = {
    "ny": "New York",
    "nyc": "New York",
    "new york city": "New York",
    "sf": "San Francisco",
    "la": "Los Angeles",
    "dc": "Washington",
    "d.c.": "Washington",
}

COUNTRY_ALIASES: dict[str, str] = {
    "usa": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "uae": "United Arab Emirates",
}


def _norm_key_name(name: str) -> str:
    """Key for fuzzy dedup only."""
    s = clean_str(name).lower()
    s = re.sub(r"\b(llc|l\.l\.c\.|ltd|limited|inc|incorporated|plc|lp|l\.p\.)\b", "", s, flags=re.I)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return normalize_whitespace(s)


def normalize_aum_display(raw: Any) -> str:
    s = clean_str(raw)
    if not s:
        return ""
    s = s.replace("~", "").replace("≈", "").strip()
    s = re.sub(r"\s+", " ", s)
    # Light canonicalization: leading $ optional space
    s = re.sub(r"\$\s*", "$", s)
    return s


def normalize_city(city: Any) -> str:
    c = clean_str(city)
    if not c:
        return ""
    key = c.lower().strip(".")
    return US_CITY_ALIASES.get(key, c)


def normalize_country(country: Any) -> str:
    c = clean_str(country)
    if not c:
        return ""
    key = c.lower().strip(".")
    return COUNTRY_ALIASES.get(key, c)


def add_normalization_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_norm_fo_name_key"] = out["FO Name"].map(_norm_key_name)
    out["HQ City Normalized"] = out["HQ City"].map(normalize_city)
    out["HQ Country Normalized"] = out["HQ Country"].map(normalize_country)
    out["AUM Normalized"] = out["AUM Est. (USD)"].map(normalize_aum_display)
    # City/country mismatch heuristic: flag if city is US alias but country not US-like
    mismatch: list[str] = []
    for _, row in out.iterrows():
        city = clean_str(row.get("HQ City Normalized", "")).lower()
        country = clean_str(row.get("HQ Country Normalized", "")).lower()
        note = ""
        us_cities = {"new york", "san francisco", "los angeles", "chicago", "houston", "boston", "miami", "seattle"}
        if city in us_cities and country and country not in {"united states", "usa", "us"}:
            note = "possible_city_country_mismatch"
        mismatch.append(note)
    out["_geo_mismatch_flag"] = mismatch
    return out


def find_near_duplicates(df: pd.DataFrame, threshold: int = 88) -> pd.DataFrame:
    """Pairs of rows with similar normalized FO names."""
    rows: list[dict[str, Any]] = []
    names = df["_norm_fo_name_key"].tolist()
    display = df["FO Name"].tolist()
    idxs = df.index.tolist()
    for (i, a), (j, b) in combinations(enumerate(idxs), 2):
        score = fuzz.ratio(names[i], names[j])
        if score >= threshold:
            rows.append(
                {
                    "row_a_index": int(a),
                    "row_b_index": int(b),
                    "fo_name_a": display[i],
                    "fo_name_b": display[j],
                    "fuzzy_score": score,
                }
            )
    return pd.DataFrame(rows)


def write_dedup_report(df: pd.DataFrame, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dupes = find_near_duplicates(df)
    dupes.to_csv(out_path, index=False)
    return len(dupes)
