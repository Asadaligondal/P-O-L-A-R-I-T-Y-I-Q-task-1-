#!/usr/bin/env python3
"""
Validate family_offices_normalised.csv and write validation_report.json.

Checks:
  1) LinkedIn URL — HEAD (non-Undisclosed https URLs), flag 404 / authwall / login
  2) needs_enrichment — reads ``completeness_score`` from CSV when present, and
     always computes **signal_13** (13 signal fields, non-empty, not Undisclosed) / 13.
     Flags when **either** score is **< 0.5** (so sparse principals are caught even
     if normalize’s broader /19 CSV score stayed high). If the CSV column is missing,
     only **signal_13** applies.
  3) HIGH confidence without a real primary_source URL → confidence_mismatch

Prints flagged rows and a diagnostic list for ``signal_13 < 0.5``.

Run:  python validate.py
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ENRICHMENT_THRESHOLD = 0.5

# 13 “signal” fields — filled only if non-empty and not Undisclosed (case-insensitive)
SIGNAL_FIELDS = [
    "principal_name",
    "principal_title",
    "principal_linkedin",
    "principal_email",
    "aum_usd_est",
    "check_size_est",
    "recent_signals",
    "investment_focus",
    "geographic_mandate",
    "hq_city",
    "hq_country",
    "primary_source",
    "secondary_source",
]
SIGNAL_DENOM = len(SIGNAL_FIELDS)  # 13

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _clean(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def is_undisclosed_or_empty(s: str) -> bool:
    """Aligned with normalize.py: placeholders do not count as filled."""
    t = _clean(s).lower().rstrip(".")
    if not t:
        return True
    if t in {"undisclosed", "unknown", "n/a", "na", "-", "none", "null", "undisclosed (see notes)"}:
        return True
    if t == "undisclosed" or t.startswith("undisclosed(") or t.startswith("undisclosed ("):
        return True
    if t.startswith("undisclosed"):
        return True
    return False


_SIGNAL_PRINCIPAL_DEP = frozenset(
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


def _signal_field_filled(row: pd.Series, col: str) -> bool:
    if col not in row.index:
        return False
    if is_undisclosed_or_empty(row.get(col, "")):
        return False
    if col in _SIGNAL_PRINCIPAL_DEP and is_undisclosed_or_empty(row.get("principal_name", "")):
        return False
    return True


def field_counts_for_signal(row: pd.Series) -> tuple[int, int]:
    """Return (filled_count, SIGNAL_DENOM) for the 13 signal columns."""
    filled = sum(1 for col in SIGNAL_FIELDS if _signal_field_filled(row, col))
    return filled, SIGNAL_DENOM


def compute_signal_completeness(row: pd.Series) -> float:
    """13-field score: count non-empty, non-Undisclosed / 13."""
    filled, denom = field_counts_for_signal(row)
    return round(filled / denom, 4) if denom else 0.0


def parse_csv_completeness(row: pd.Series) -> float | None:
    """Return float from CSV completeness_score column, or None if missing/invalid."""
    if "completeness_score" not in row.index:
        return None
    v = row.get("completeness_score")
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def enrichment_scores(csv_score: float | None, signal_score: float) -> tuple[bool, float]:
    """
    Returns (needs_flag, display_score_for_sorting).
    Flag if signal_13 < threshold OR (csv present and csv < threshold).
    display_score uses min(csv, signal) when both exist so the print block sorts
    by the stricter of the two.
    """
    sig = round(float(signal_score), 4)
    weak_signal = sig < ENRICHMENT_THRESHOLD
    weak_csv = csv_score is not None and float(csv_score) < ENRICHMENT_THRESHOLD
    flag = weak_signal or weak_csv
    if csv_score is not None:
        disp = round(min(float(csv_score), sig), 4)
    else:
        disp = sig
    return flag, disp


def check_linkedin(url: str) -> tuple[bool, str]:
    """
    Returns (broken, detail).
    broken=True only if status is 404 OR final URL indicates authwall/login
    (per spec). Other status codes are not auto-flagged; request errors are
    reported as broken so they can be retried manually.
    """
    u = _clean(url)
    if not u.lower().startswith("https://"):
        return False, "skipped_not_https"
    if "linkedin.com" not in u.lower():
        return False, "skipped_not_linkedin"

    headers = {"User-Agent": BROWSER_UA}
    try:
        r = requests.head(u, allow_redirects=True, timeout=20, headers=headers)
        final = (r.url or "").lower()
        code = r.status_code
        if code == 404:
            return True, "http_404"
        if "authwall" in final or "login" in final or "signin" in final:
            return True, f"login_wall url={r.url[:160]}"
        return False, f"ok_http_{code}"
    except requests.RequestException as e:
        return True, f"request_error:{str(e)[:120]}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate normalised family office CSV.")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path("family_offices_normalised.csv"),
        help="Path to family_offices_normalised.csv",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("validation_report.json"),
        help="Path for validation_report.json",
    )
    args = ap.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Input not found: {args.input.resolve()}")

    df = pd.read_csv(args.input)
    df = df.dropna(how="all")

    linkedin_broken_n = 0
    needs_enrichment_n = 0
    confidence_mismatch_n = 0
    passed_all = 0

    flagged: list[dict[str, Any]] = []
    linkedin_checked = 0
    below_threshold: list[tuple[str, float | None, float, float, bool]] = []

    for idx, row in df.iterrows():
        fo_name = _clean(row.get("fo_name", "")) or f"(row {idx})"
        flags: list[str] = []
        detail_parts: list[str] = []

        signal_score = compute_signal_completeness(row)
        csv_score = parse_csv_completeness(row)
        need_enrich, disp_score = enrichment_scores(csv_score, signal_score)

        if need_enrich:
            flags.append("needs_enrichment")
            csv_part = f"{csv_score:.4f}" if csv_score is not None else "n/a"
            detail_parts.append(
                f"needs_enrichment: csv={csv_part} signal_13={signal_score:.4f} "
                f"(flag if either < {ENRICHMENT_THRESHOLD}; display_min={disp_score})"
            )
            needs_enrichment_n += 1

        below_threshold.append((fo_name, csv_score, signal_score, disp_score, need_enrich))

        # --- Check 3: HIGH confidence vs primary source ---
        conf_raw = _clean(row.get("confidence_score", ""))
        conf_u = conf_raw.upper()
        primary = row.get("primary_source", "")
        if conf_u == "HIGH" and is_undisclosed_or_empty(primary):
            flags.append("confidence_mismatch")
            detail_parts.append("HIGH confidence but primary_source empty/Undisclosed")
            confidence_mismatch_n += 1

        # --- Check 1: LinkedIn HEAD ---
        li = row.get("principal_linkedin", "")
        li_s = _clean(li)
        if (
            li_s
            and not is_undisclosed_or_empty(li_s)
            and li_s.lower().startswith("https://")
        ):
            linkedin_checked += 1
            broken, li_detail = check_linkedin(li_s)
            if broken:
                flags.append("linkedin_broken")
                detail_parts.append(f"linkedin:{li_detail}")
                linkedin_broken_n += 1
            time.sleep(1.0)

        if flags:
            flagged.append(
                {
                    "fo_name": fo_name,
                    "flags": flags,
                    "details": " | ".join(detail_parts),
                }
            )
        else:
            passed_all += 1

    report = {
        "summary": {
            "total_records": int(len(df)),
            "linkedin_broken": linkedin_broken_n,
            "needs_enrichment": needs_enrichment_n,
            "confidence_mismatch": confidence_mismatch_n,
            "passed_all_checks": passed_all,
            "enrichment_threshold": ENRICHMENT_THRESHOLD,
        },
        "flagged_records": flagged,
    }

    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    s = report["summary"]
    print()
    print("Validation complete")
    print("=" * 48)
    print(f"  Input:           {args.input}")
    print(f"  Report written: {args.output}")
    print("-" * 48)
    print(f"  Total records:        {s['total_records']}")
    print(f"  LinkedIn URLs checked:{linkedin_checked} (HEAD, 1s delay between)")
    print(f"  linkedin_broken:      {s['linkedin_broken']}")
    print(
        f"  needs_enrichment:     {s['needs_enrichment']} "
        f"(csv or signal_13 < {ENRICHMENT_THRESHOLD})"
    )
    print(f"  confidence_mismatch:  {s['confidence_mismatch']}")
    print(f"  passed_all_checks:    {s['passed_all_checks']}")
    print("=" * 48)

    # (a) Flagged by rule (2)
    low_flagged = [t for t in below_threshold if t[4]]
    print()
    print(f"Records flagged needs_enrichment: {len(low_flagged)}")
    print("-" * 88)
    for name, csv_s, sig, disp, _ in sorted(low_flagged, key=lambda x: x[3]):
        csv_part = f"{csv_s:.4f}" if csv_s is not None else "n/a"
        print(
            f"  {name[:40]:<40}  min(csv,signal)={disp:.4f}  csv={csv_part:<8}  signal_13={sig:.4f}"
        )
    print("-" * 88)

    # (b) All rows with weak 13-field signal
    low_sig = [t for t in below_threshold if t[2] < ENRICHMENT_THRESHOLD]
    print()
    print(f"Diagnostic - rows with signal_13 < {ENRICHMENT_THRESHOLD}: {len(low_sig)}")
    print("-" * 88)
    for name, csv_s, sig, disp, flagged in sorted(low_sig, key=lambda x: x[2]):
        csv_part = f"{csv_s:.4f}" if csv_s is not None else "n/a"
        mk = "*" if flagged else " "
        print(
            f" {mk} {name[:38]:<38}  signal_13={sig:.4f}  csv={csv_part:<8}  min={disp:.4f}"
        )
    print("-" * 88)
    print()


if __name__ == "__main__":
    main()
