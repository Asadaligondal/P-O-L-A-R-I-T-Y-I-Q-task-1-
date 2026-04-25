"""
Two-stage hybrid retrieval for ChromaDB + sentence-transformers.

Stage 1 — Structured filter parse (regex / heuristics only, no LLM):
  Inspect the user query for AUM thresholds, HQ city, HQ country, FO type,
  and confidence level. Build a Chroma ``where`` metadata filter when possible.

Stage 2 — Semantic retrieval:
  Run ``collection.query`` with the same query text, but *restricted* to rows
  matching the Stage-1 filter. If Stage 1 finds no structured filters,
  ``where`` is omitted and search runs on the full collection.

Expected metadata keys on each embedding (see ``src/documents.py``):
  ``aum_tier``, ``hq_city``, ``hq_country``, ``fo_type``, ``confidence_score``
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# AUM tier model (must match values stored at ingest time on ``aum_tier``)
# Each tuple: (label, lower_bound_usd, upper_bound_usd) with upper=inf for top.
# ---------------------------------------------------------------------------
AUM_TIERS: list[tuple[str, float, float]] = [
    ("200B+", 200e9, float("inf")),
    ("50B-200B", 50e9, 200e9),
    ("1B-50B", 1e9, 50e9),
]


def infer_aum_tier_from_text(*parts: str) -> str:
    """
    Map free-text AUM (e.g. '$90-100B', '$1B+', 'Undisclosed') to a coarse tier
    label used in Chroma metadata. Conservative → ``unknown`` when unclear.
    """
    blob = " ".join(p for p in parts if p).lower().replace(",", "")
    if not blob or "undisclosed" in blob or "unknown" in blob or "n/a" in blob:
        return "unknown"

    # Explicit 200B+ style
    if re.search(r"200\s*b\s*\+|>\s*200\s*b|≥\s*200\s*b", blob):
        return "200B+"

    # Range like 90-100b, 50–200b
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*b", blob)
    if m:
        lo, hi = float(m.group(1)) * 1e9, float(m.group(2)) * 1e9
        mid = (lo + hi) / 2
        return _point_to_tier(mid)

    # Single number + b / billion
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(b|bn|billion)\b", blob)
    if m:
        v = float(m.group(1)) * 1e9
        return _point_to_tier(v)

    # Millions → tier by dividing into billions scale
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(m|mm|million)\b", blob)
    if m:
        v = float(m.group(1)) * 1e6
        return _point_to_tier(v)

    return "unknown"


def _point_to_tier(usd: float) -> str:
    if usd < 1e9:
        return "unknown"
    for label, lo, hi in AUM_TIERS:
        if lo <= usd <= hi:
            return label
    if usd > 200e9:
        return "200B+"
    return "unknown"


def tiers_intersecting_at_least(threshold_usd: float) -> list[str]:
    """Tiers that could plausibly contain an office with AUM >= threshold."""
    out: list[str] = []
    for label, lo, hi in AUM_TIERS:
        if hi >= threshold_usd:
            out.append(label)
    return out or []


def tiers_intersecting_below(threshold_usd: float) -> list[str]:
    """Tiers that could plausibly contain an office with AUM < threshold."""
    out: list[str] = []
    for label, lo, hi in AUM_TIERS:
        if lo < threshold_usd:
            out.append(label)
    return out or []


# ---------------------------------------------------------------------------
# Stage 1 — Query → Chroma ``where`` (pattern matching only)
# ---------------------------------------------------------------------------
@dataclass
class ParsedFilters:
    """Human-readable summary of what Stage 1 extracted."""

    chroma_where: dict[str, Any] | None
    aum_tiers: list[str] | None
    hq_city: str | None
    hq_country: str | None
    fo_type: str | None
    confidence_score: str | None


def _parse_money_threshold_usd(q: str) -> tuple[str | None, float | None]:
    """
    Detect a single dollar threshold and direction: ('at_least', usd), ('below', usd), or (None, None).
    """
    s = q.strip()
    # "above $100M", "more than 5 billion", "> $1b"
    m = re.search(
        r"(?i)(?:above|over|more\s+than|greater\s+than|at\s+least|>=?|>)\s*(?:\$)?\s*([\d.,]+)\s*(m|mm|million|b|bn|billion)?",
        s,
    )
    if m:
        return _money_match_to_threshold("at_least", m)

    m = re.search(
        r"(?i)(?:below|under|less\s+than|<=?|<)\s*(?:\$)?\s*([\d.,]+)\s*(m|mm|million|b|bn|billion)?",
        s,
    )
    if m:
        return _money_match_to_threshold("below", m)

    # "$100M+", "$5b or more"
    m = re.search(
        r"(?i)(?:\$)?\s*([\d.,]+)\s*(m|mm|million|b|bn|billion)\s*\+",
        s,
    )
    if m:
        return _money_match_to_threshold("at_least", m)

    # "AUM ... $100M" loose (treat as minimum threshold when direction omitted)
    if re.search(r"(?i)\baum\b", s):
        m = re.search(r"(?i)\$?\s*([\d.,]+)\s*(m|mm|million|b|bn|billion)\b", s)
        if m:
            return _money_match_to_threshold("at_least", m)

    return None, None


def _money_match_to_threshold(direction: str, m: re.Match[str]) -> tuple[str | None, float | None]:
    raw = m.group(1).replace(",", "")
    try:
        val = float(raw)
    except ValueError:
        return None, None
    unit = (m.group(2) or "m").lower()
    if unit.startswith("b"):
        usd = val * 1e9
    else:
        usd = val * 1e6
    return direction, usd


def _normalize_country_token(tok: str) -> str | None:
    t = tok.strip().lower()
    aliases = {
        "usa": "United States",
        "u.s.": "United States",
        "u.s.a.": "United States",
        "us": "United States",
        "united states": "United States",
        "america": "United States",
        "uk": "United Kingdom",
        "u.k.": "United Kingdom",
        "britain": "United Kingdom",
        "england": "United Kingdom",
        "uae": "United Arab Emirates",
        "singapore": "Singapore",
        "switzerland": "Switzerland",
        "monaco": "Monaco",
        "canada": "Canada",
        "france": "France",
        "germany": "Germany",
        "india": "India",
        "china": "China",
        "japan": "Japan",
        "australia": "Australia",
    }
    return aliases.get(t, tok.strip() if tok.strip() else None)


def _extract_city(q: str) -> str | None:
    s = q.strip()
    # "in New York", "based in San Francisco"
    m = re.search(
        r"(?i)(?:\bin\b|\bbased\s+in\b|\bheadquartered\s+in\b)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        s,
    )
    if m:
        return m.group(1).strip()
    return None


def _extract_country(q: str) -> str | None:
    s = q.strip()
    m = re.search(
        r"(?i)(?:\bcountry\b\s*[:]?\s*|based\s+in\s+the\s+)"
        r"((?:United\s+States|United\s+Kingdom|New\s+Zealand)|USA|UK|UAE)\b",
        s,
    )
    if m:
        return _normalize_country_token(m.group(1)) or m.group(1).strip()
    m = re.search(
        r"(?i)\bin\s+((?:United\s+States|United\s+Kingdom|New\s+Zealand)|USA|UK|UAE|Singapore|Monaco|Switzerland|Canada|France|Germany|India|Japan|Australia|China)\b",
        s,
    )
    if m:
        return _normalize_country_token(m.group(1)) or m.group(1).strip()
    return None


def _extract_fo_type(q: str) -> str | None:
    s = q.lower()
    if re.search(r"\bmfo\b|multi[-\s]?family", s):
        return "MFO"
    if re.search(r"\bsfo\b|single[-\s]?family", s):
        return "SFO"
    return None


def _extract_confidence(q: str) -> str | None:
    s = q.strip()
    m = re.search(r"(?i)\b(high|medium|low)\s+confidence\b", s)
    if m:
        return m.group(1).upper()
    m = re.search(r"(?i)\bconfidence\s*[:]?\s*(high|medium|low)\b", s)
    if m:
        return m.group(1).upper()
    return None


def build_chroma_where_clause(q: str) -> ParsedFilters:
    """
    Stage 1 entrypoint: inspect ``q`` and assemble a Chroma metadata filter.

    Chroma expects operators like ``{"field": {"$eq": "x"}}`` or
    ``{"$and": [ {...}, {...} ]}``.
    """
    clauses: list[dict[str, Any]] = []
    aum_list: list[str] | None = None
    city = _extract_city(q)
    country = _extract_country(q)
    fo_type = _extract_fo_type(q)
    conf = _extract_confidence(q)

    direction, usd = _parse_money_threshold_usd(q)
    if direction == "at_least" and usd is not None:
        aum_list = tiers_intersecting_at_least(usd)
        if aum_list:
            clauses.append({"aum_tier": {"$in": aum_list}})
    elif direction == "below" and usd is not None:
        aum_list = tiers_intersecting_below(usd)
        if aum_list:
            clauses.append({"aum_tier": {"$in": aum_list}})

    if city:
        clauses.append({"hq_city": {"$eq": city}})
    if country:
        clauses.append({"hq_country": {"$eq": country}})
    if fo_type:
        clauses.append({"fo_type": {"$eq": fo_type}})
    if conf:
        clauses.append({"confidence_score": {"$eq": conf}})

    if not clauses:
        return ParsedFilters(None, None, city, country, fo_type, conf)

    if len(clauses) == 1:
        where: dict[str, Any] = clauses[0]
    else:
        where = {"$and": clauses}

    return ParsedFilters(where, aum_list, city, country, fo_type, conf)


def merge_wheres(*clauses: dict[str, Any] | None) -> dict[str, Any] | None:
    """AND-merge Chroma metadata ``where`` fragments (drop Nones)."""
    parts = [c for c in clauses if c]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


# ---------------------------------------------------------------------------
# Stage 2 — Semantic search on filtered subset (or full collection)
# ---------------------------------------------------------------------------
def hybrid_query_collection(
    collection: Any,
    query_text: str,
    n_results: int = 6,
    parsed: ParsedFilters | None = None,
    extra_where: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run Chroma ``query`` with optional ``where`` from Stage 1.

    ``extra_where`` (e.g. Streamlit sidebar filters) is AND-merged with the
    query-derived ``parsed.chroma_where`` before semantic search.
    """
    pf = parsed or build_chroma_where_clause(query_text)
    combined = merge_wheres(extra_where, pf.chroma_where)
    kwargs: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if combined is not None:
        kwargs["where"] = combined
    return collection.query(**kwargs)
