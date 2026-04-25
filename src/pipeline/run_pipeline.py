"""
Run the full data pipeline in evaluation order: 3 → 2 → 1 → 4 → 5.

(Step 6 — prose chunks — is applied at ingest via `src.documents`.)

Writes:
  artifacts/dataset_for_rag.xlsx
  artifacts/dedup_report.csv
  artifacts/enrichment_queue.csv
  artifacts/pipeline_summary.txt
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..config import ARTIFACTS_DIR, DATA_ARTIFACT_XLSX, DATA_SHEET, DATA_XLSX
from .completeness import add_completeness_columns
from .enrich_suggest import build_enrichment_queue
from .normalize import add_normalization_columns, write_dedup_report
from .signal_freshness import add_signal_age
from .validate_records import add_skipped_validation_columns, run_validation_columns


def load_source(path: Path | None = None) -> pd.DataFrame:
    p = path or DATA_XLSX
    if not p.is_file():
        raise FileNotFoundError(f"Missing source workbook: {p}")
    df = pd.read_excel(p, sheet_name=DATA_SHEET)
    return df.dropna(how="all")


def run_pipeline(
    input_path: Path | None = None,
    skip_validation: bool = False,
    pause_sec: float = 0.35,
) -> Path:
    df = load_source(input_path)

    # 3 — Normalize + dedup report
    df = add_normalization_columns(df)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    n_pairs = write_dedup_report(df, ARTIFACTS_DIR / "dedup_report.csv")

    # 2 — Completeness
    df = add_completeness_columns(df)

    # 1 — Automated validation (network)
    if skip_validation:
        df = add_skipped_validation_columns(df)
    else:
        df = run_validation_columns(df, pause_sec=pause_sec)

    # 4 — Enrichment queue (CSV only)
    n_queue = build_enrichment_queue(df, ARTIFACTS_DIR / "enrichment_queue.csv")

    # 5 — Signal freshness
    df = add_signal_age(df)

    out_xlsx = DATA_ARTIFACT_XLSX
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=DATA_SHEET, index=False)

    summary = f"""Pipeline run at {datetime.now(timezone.utc).isoformat()}
Input: {input_path or DATA_XLSX}
Output: {out_xlsx}
Rows: {len(df)}
Near-duplicate name pairs (fuzzy): {n_pairs}
Enrichment queue rows: {n_queue}
Validation: {"SKIPPED" if skip_validation else "EXECUTED"}

SEC note: set SEC_USER_AGENT to a string identifying you (see https://www.sec.gov/os/webmaster-faq#code-support).
"""
    (ARTIFACTS_DIR / "pipeline_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)
    return out_xlsx


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FO dataset quality pipeline.")
    parser.add_argument("--input", type=Path, default=None, help="Override source XLSX path.")
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip network calls (LinkedIn, SEC, Google News RSS).",
    )
    parser.add_argument("--pause-sec", type=float, default=0.35, help="Delay between network rows.")
    args = parser.parse_args()
    run_pipeline(input_path=args.input, skip_validation=args.skip_validation, pause_sec=args.pause_sec)


if __name__ == "__main__":
    main()
