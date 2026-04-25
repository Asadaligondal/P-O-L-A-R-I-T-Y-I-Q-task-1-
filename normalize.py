#!/usr/bin/env python3
"""
Script 1 — Normalise family-office CSV for RAG.

Input:  family_offices_rag_ready.csv (snake_case) OR the same rows with
        Excel-style headers from family_office_dataset_50_records.xlsx export.
Output: family_offices_normalised.csv (+ aum_tier, completeness_score)

Run from repo root:
  python normalize.py
  python normalize.py --input path/to.csv --output path/out.csv
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

# --- Canonical column names (target schema) ---------------------------------
CANON_COLS = [
    "fo_name",
    "fo_type",
    "hq_city",
    "hq_country",
    "aum_usd_est",
    "principal_name",
    "principal_title",
    "principal_linkedin",
    "principal_email",
    "investment_focus",
    "geographic_mandate",
    "check_size_est",
    "recent_signals",
    "primary_source",
    "secondary_source",
    "confidence_score",
    "confidence_reason",
    "last_validated",
    "notes",
]

# 19 fields for completeness denominator (matches prompt + principal_email slot)
COMPLETENESS_FIELDS = CANON_COLS
DENOMINATOR = len(COMPLETENESS_FIELDS)

# Map headers from your Excel workbook export → snake_case
EXCEL_TO_CANON = {
    "FO Name": "fo_name",
    "FO Type (SFO/MFO)": "fo_type",
    "HQ City": "hq_city",
    "HQ Country": "hq_country",
    "AUM Est. (USD)": "aum_usd_est",
    "Principal Name": "principal_name",
    "Principal Title": "principal_title",
    "Principal LinkedIn": "principal_linkedin",
    "Principal Email": "principal_email",
    "Investment Focus": "investment_focus",
    "Geographic Mandate": "geographic_mandate",
    "Check Size Est.": "check_size_est",
    "Recent Signals / Activity": "recent_signals",
    "Primary Source": "primary_source",
    "Secondary Source": "secondary_source",
    "Confidence Score": "confidence_score",
    "Confidence Reason": "confidence_reason",
    "Last Validated": "last_validated",
    "Notes / Caveats": "notes",
}

EMPTY_TOKENS = frozenset(
    {
        "",
        "n/a",
        "na",
        "none",
        "unknown",
        "undisclosed",
        "undisclosed (see notes)",
        "tbd",
        "—",
        "-",
        "null",
    }
)

COUNTRY_MAP = {
    "united states": "USA",
    "united states of america": "USA",
    "usa": "USA",
    "u.s.": "USA",
    "u.s.a.": "USA",
    "us": "USA",
    "america": "USA",
    "united kingdom": "UK",
    "u.k.": "UK",
    "uk": "UK",
    "britain": "UK",
    "england": "UK",
    "great britain": "UK",
    "germany": "Germany",
    "france": "France",
    "switzerland": "Switzerland",
    "monaco": "Monaco",
    "singapore": "Singapore",
    "uae": "UAE",
    "united arab emirates": "UAE",
    "canada": "Canada",
    "india": "India",
    "china": "China",
    "japan": "Japan",
    "australia": "Australia",
    "hong kong": "Hong Kong",
    "netherlands": "Netherlands",
    "luxembourg": "Luxembourg",
    "ireland": "Ireland",
    "brazil": "Brazil",
    "mexico": "Mexico",
    "south africa": "South Africa",
    "new zealand": "New Zealand",
}


def _clean_cell(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def is_empty_for_score(v: object) -> bool:
    """
    A field counts as NOT populated for completeness if empty, whitespace-only,
    or placeholder text (Undisclosed in any common form, N/A, etc.).
    """
    s = _clean_cell(v).lower().rstrip(".")
    if not s:
        return True
    if s in EMPTY_TOKENS:
        return True
    # Any value that is / starts as an Undisclosed placeholder
    if s == "undisclosed" or s.startswith("undisclosed(") or s.startswith("undisclosed ("):
        return True
    if s.startswith("undisclosed"):
        return True
    return False


# Do not count narrative / sizing fields unless there is a real principal identity.
_PRINCIPAL_DEPENDENT = frozenset(
    {
        "principal_title",
        "principal_linkedin",
        "principal_email",
        "check_size_est",
        "recent_signals",
        "investment_focus",
        "geographic_mandate",
    }
)


def is_field_filled_for_completeness(row: pd.Series, col: str) -> bool:
    if col not in row.index:
        return False
    if is_empty_for_score(row.get(col, "")):
        return False
    if col in _PRINCIPAL_DEPENDENT and is_empty_for_score(row.get("principal_name", "")):
        return False
    return True


def standardise_country(raw: object) -> str:
    s = _clean_cell(raw)
    if not s:
        return ""
    key = s.lower().strip().rstrip(".")
    return COUNTRY_MAP.get(key, s)


def standardise_fo_type(raw: object) -> str:
    s = _clean_cell(raw).upper()
    if not s or s in {"N/A", "UNKNOWN"}:
        return "Undisclosed"
    if "MFO" in s or "MULTI" in s:
        return "MFO"
    if "SFO" in s or "SINGLE" in s:
        return "SFO"
    return "Undisclosed"


def _parse_billions_pair(blob: str) -> tuple[float | None, float | None]:
    """Return (min_usd, max_usd) in dollars from first range or single value in B/M."""
    blob = blob.lower().replace(",", "")
    if not blob:
        return None, None
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*b", blob)
    if m:
        lo = float(m.group(1)) * 1e9
        hi = float(m.group(2)) * 1e9
        return min(lo, hi), max(lo, hi)
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(b|bn|billion)\b", blob)
    if m:
        v = float(m.group(1)) * 1e9
        return v, v
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(m|mm|million)\b", blob)
    if m:
        v = float(m.group(1)) * 1e6
        return v, v
    return None, None


def extract_aum_tier(aum_text: object) -> str:
    """
    Tier rules from prompt:
      $200B+ / 200B+ → 200B+
      $50B–$200B (or overlapping that band) → 50B-200B
      $1B–$50B → 1B-50B
      Parsed max < $1B → under-1B
      Undisclosed / missing → unknown

    Wide or ambiguous ranges are bucketed by the **midpoint** of (lo, hi) in USD.
    """
    raw = _clean_cell(aum_text)
    low = raw.lower()
    if not raw or "undisclosed" in low or "unknown" in low or low in {"n/a", "-", "—"}:
        return "unknown"

    if re.search(r"200\s*b\s*\+|\$?\s*200\s*b\s*\+", low):
        return "200B+"

    lo, hi = _parse_billions_pair(low)
    if lo is None or hi is None:
        return "unknown"

    if hi < 1e9:
        return "under-1B"

    mid = (lo + hi) / 2.0
    if mid >= 200e9:
        return "200B+"
    if mid >= 50e9:
        return "50B-200B"
    if mid >= 1e9:
        return "1B-50B"
    return "under-1B"


def completeness_score_row(row: pd.Series) -> float:
    filled = sum(1 for c in COMPLETENESS_FIELDS if is_field_filled_for_completeness(row, c))
    return round(filled / DENOMINATOR, 4) if DENOMINATOR else 0.0


def ensure_canonical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Excel export headers to snake_case; add missing optional columns."""
    rename = {k: v for k, v in EXCEL_TO_CANON.items() if k in df.columns}
    if rename:
        df = df.rename(columns=rename)
    for c in CANON_COLS:
        if c not in df.columns:
            df[c] = ""
    return df[CANON_COLS].copy()


def main() -> None:
    ap = argparse.ArgumentParser(description="Normalise family office CSV for RAG.")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path("family_offices_rag_ready.csv"),
        help="Input CSV path",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("family_offices_normalised.csv"),
        help="Output CSV path",
    )
    args = ap.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Input not found: {args.input.resolve()}")

    df = pd.read_csv(args.input)
    df = ensure_canonical_columns(df)

    df["hq_country"] = df["hq_country"].map(standardise_country)
    df["fo_type"] = df["fo_type"].map(standardise_fo_type)
    df["aum_tier"] = df["aum_usd_est"].map(extract_aum_tier)
    df["completeness_score"] = [completeness_score_row(df.loc[i]) for i in df.index]

    out_cols = CANON_COLS + ["aum_tier", "completeness_score"]
    for c in out_cols:
        if c not in df.columns:
            df[c] = ""
    df[out_cols].to_csv(args.output, index=False)
    print(f"Wrote {args.output.resolve()} ({len(df)} rows).")


if __name__ == "__main__":
    main()
