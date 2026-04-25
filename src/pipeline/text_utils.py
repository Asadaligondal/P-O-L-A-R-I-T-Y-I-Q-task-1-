"""Shared text helpers for pipeline stages."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

EMPTY_TOKENS = frozenset(
    {
        "",
        "n/a",
        "na",
        "none",
        "unknown",
        "undisclosed",
        "tbd",
        "—",
        "-",
        "null",
    }
)


def clean_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    return s


def is_empty_value(value: Any) -> bool:
    s = clean_str(value).lower()
    if not s:
        return True
    return s.lower() in EMPTY_TOKENS


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def extract_years(text: str) -> list[int]:
    if not text:
        return []
    out: list[int] = []
    for m in re.finditer(r"\b(20[0-2][0-9])\b", text):
        y = int(m.group(1))
        if 2000 <= y <= 2035:
            out.append(y)
    return out
