"""Step 5: Signal recency bucket from free-text signals + last validated."""
from __future__ import annotations

import pandas as pd

from .text_utils import clean_str, extract_years, is_empty_value

BUCKETS = ("2025", "2024", "2023-or-older", "unknown")


def _bucket_from_max_year(max_year: int | None) -> str:
    if max_year is None:
        return "unknown"
    if max_year >= 2025:
        return "2025"
    if max_year == 2024:
        return "2024"
    return "2023-or-older"


def signal_age_for_row(row: pd.Series) -> str:
    parts: list[str] = []
    sig = clean_str(row.get("Recent Signals / Activity", ""))
    if not is_empty_value(sig):
        parts.append(sig)
    lv = clean_str(row.get("Last Validated", ""))
    if not is_empty_value(lv):
        parts.append(lv)
    years = extract_years(" ".join(parts))
    max_y = max(years) if years else None
    return _bucket_from_max_year(max_y)


def add_signal_age(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["signal_age"] = [signal_age_for_row(out.loc[i]) for i in out.index]
    return out
