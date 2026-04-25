"""Step 6: Human-readable paragraph per row for embedding quality."""
from __future__ import annotations

import pandas as pd

from .text_utils import clean_str, is_empty_value


def row_to_prose(row: pd.Series) -> str:
    """Single dense paragraph; uses normalized columns when present."""
    name = clean_str(row.get("FO Name", ""))
    fo_type = clean_str(row.get("FO Type (SFO/MFO)", ""))
    city = clean_str(row.get("HQ City Normalized", "")) or clean_str(row.get("HQ City", ""))
    country = clean_str(row.get("HQ Country Normalized", "")) or clean_str(row.get("HQ Country", ""))
    hq = ""
    if city and country:
        hq = f"headquartered in {city}, {country}"
    elif country:
        hq = f"based in {country}"
    elif city:
        hq = f"headquartered in {city}"

    lead = name
    if fo_type and hq:
        lead = f"{name} is a {fo_type} {hq}."
    elif fo_type:
        lead = f"{name} is a {fo_type}."
    elif hq:
        lead = f"{name} is a family office {hq}."
    else:
        lead = f"{name} is a family office."

    bits: list[str] = [lead]

    aum = clean_str(row.get("AUM Normalized", "")) or clean_str(row.get("AUM Est. (USD)", ""))
    if not is_empty_value(aum):
        bits.append(f"Estimated assets under management are approximately {aum}.")

    principal = clean_str(row.get("Principal Name", ""))
    title = clean_str(row.get("Principal Title", ""))
    if not is_empty_value(principal):
        t = f", {title}" if title else ""
        bits.append(f"Key leadership includes {principal}{t}.")

    focus = clean_str(row.get("Investment Focus", ""))
    if not is_empty_value(focus):
        bits.append(f"Investment focus includes {focus}.")

    mandate = clean_str(row.get("Geographic Mandate", ""))
    if not is_empty_value(mandate):
        bits.append(f"Geographic mandate: {mandate}.")

    check = clean_str(row.get("Check Size Est.", ""))
    if not is_empty_value(check):
        bits.append(f"Estimated check size: {check}.")

    signals = clean_str(row.get("Recent Signals / Activity", ""))
    if not is_empty_value(signals):
        bits.append(f"Recent signals and activity: {signals}.")

    sage = clean_str(row.get("signal_age", ""))
    if sage and sage != "unknown":
        bits.append(f"Signal recency bucket: {sage}.")

    comp = row.get("Completeness Score", None)
    if comp is not None and not (isinstance(comp, float) and pd.isna(comp)):
        try:
            bits.append(f"Dataset completeness score (filled core fields): {float(comp):.2f}.")
        except (TypeError, ValueError):
            pass

    pconf = clean_str(row.get("programmatic_confidence", ""))
    if pconf:
        bits.append(f"Automated validation tier: {pconf}.")

    ps = clean_str(row.get("Primary Source", ""))
    ss = clean_str(row.get("Secondary Source", ""))
    if ps:
        bits.append(f"Primary source: {ps}.")
    if ss:
        bits.append(f"Secondary source: {ss}.")

    conf = clean_str(row.get("Confidence Score", ""))
    reason = clean_str(row.get("Confidence Reason", ""))
    if conf:
        bits.append(f"Human-assigned confidence: {conf}.")
    if reason:
        bits.append(f"Confidence rationale: {reason}")

    notes = clean_str(row.get("Notes / Caveats", ""))
    if not is_empty_value(notes):
        bits.append(f"Notes: {notes}.")

    return " ".join(bits)
