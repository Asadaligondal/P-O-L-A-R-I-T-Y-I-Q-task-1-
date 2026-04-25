"""Step 2: Data completeness scoring per row."""
from __future__ import annotations

import pandas as pd

from .text_utils import is_empty_value

# Core fields used for RAG quality (subset of sheet columns).
SCORED_COLUMNS: list[str] = [
    "FO Name",
    "FO Type (SFO/MFO)",
    "HQ City",
    "HQ Country",
    "AUM Est. (USD)",
    "Principal Name",
    "Principal Title",
    "Principal LinkedIn",
    "Principal Email",
    "Investment Focus",
    "Geographic Mandate",
    "Check Size Est.",
    "Recent Signals / Activity",
    "Primary Source",
    "Secondary Source",
    "Confidence Score",
    "Confidence Reason",
    "Last Validated",
    "Notes / Caveats",
]

_PRINCIPAL_DEP = frozenset(
    {
        "Principal Title",
        "Principal LinkedIn",
        "Principal Email",
        "Check Size Est.",
        "Recent Signals / Activity",
        "Investment Focus",
        "Geographic Mandate",
    }
)


def _scored_field_filled(row: pd.Series, col: str) -> bool:
    if col not in row.index:
        return False
    if is_empty_value(row.get(col)):
        return False
    if col in _PRINCIPAL_DEP and is_empty_value(row.get("Principal Name")):
        return False
    return True


def completeness_fraction(row: pd.Series) -> tuple[int, int, float]:
    filled = sum(1 for col in SCORED_COLUMNS if _scored_field_filled(row, col))
    total = len(SCORED_COLUMNS)
    return filled, total, (filled / total) if total else 0.0


def add_completeness_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    scores: list[int] = []
    totals: list[int] = []
    fracs: list[float] = []
    for _, row in out.iterrows():
        f, t, frac = completeness_fraction(row)
        scores.append(f)
        totals.append(t)
        fracs.append(round(frac, 4))
    out["_completeness_filled"] = scores
    out["_completeness_total"] = totals
    out["Completeness Score"] = fracs
    return out
