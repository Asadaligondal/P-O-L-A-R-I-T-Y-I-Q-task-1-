"""
Step 4: Enrichment queue — does NOT scrape LinkedIn.

Emits suggested web search URLs for rows with missing principals or low completeness.
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path

import pandas as pd

from .completeness import completeness_fraction
from .text_utils import is_empty_value


def _google_search_url(query: str) -> str:
    q = urllib.parse.quote_plus(query)
    return f"https://www.google.com/search?q={q}"


def build_enrichment_queue(df: pd.DataFrame, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str | float]] = []
    for idx, row in df.iterrows():
        name = str(row.get("FO Name", "")).strip()
        if not name:
            continue
        principal_missing = is_empty_value(row.get("Principal Name", ""))
        conf = str(row.get("Confidence Score", "")).strip().upper()
        filled, total, frac = completeness_fraction(row)
        needs = principal_missing or frac < 0.65 or conf == "LOW"
        if not needs:
            continue
        query = f'{name} family office principal OR "managing director"'
        rows.append(
            {
                "row_index": int(idx),
                "FO Name": name,
                "Principal Name": str(row.get("Principal Name", "")),
                "Completeness": f"{filled}/{total}",
                "Confidence Score": str(row.get("Confidence Score", "")),
                "suggested_search_url": _google_search_url(query),
                "note": "Manual research only; do not automate LinkedIn login or scraping.",
            }
        )
    qdf = pd.DataFrame(rows)
    qdf.to_csv(out_path, index=False)
    return len(qdf)
