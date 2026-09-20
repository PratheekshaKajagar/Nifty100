"""
src/analytics/capital_allocation.py
-------------------------------------
Module 2 (Financial Ratio Engine), Feature 2.10 - Capital Allocation
Classifier. Deliverable D-06.

`output/capital_allocation.csv` was previously a static, hand-produced
file with no script anywhere in the pipeline that could regenerate it -
`src/analytics/capital_allocation_report.py` only *verifies* coverage
of the file, it never builds it. That meant the moment the underlying
cash flow data changed (e.g. the Sprint 6 financial_ratios backfill),
this deliverable silently went stale with no way to refresh it via
`make load` / `make ratios`.

This module closes that gap: for every (company_id, year) row in the
`cashflow` table it classifies the CFO/CFI/CFF sign pattern using the
existing `capital_allocation_pattern()` formula in
`src/analytics/cashflow_kpis.py` (the same 7-pattern + "Unknown"
mapping described in Section 13 of the project spec) and writes the
result to `output/capital_allocation.csv` in the same
company_id / year / cfo_sign / cfi_sign / cff_sign / pattern_label
shape the file always had.

Run with:
    PYTHONPATH=. python3 src/analytics/capital_allocation.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cashflow_kpis import capital_allocation_pattern

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "capital_allocation.csv"


def build_capital_allocation_table(db_path=DEFAULT_DB_PATH):
    """
    Classify every (company_id, year) cash flow row into one of the
    8 capital-allocation patterns. Returns the resulting DataFrame.
    """
    conn = sqlite3.connect(db_path)
    cf = pd.read_sql(
        "SELECT company_id, year, operating_activity, investing_activity, "
        "financing_activity FROM cashflow",
        conn,
    )
    conn.close()

    rows = []
    for _, r in cf.iterrows():
        cfo, cfi, cff = r["operating_activity"], r["investing_activity"], r["financing_activity"]
        if pd.isna(cfo) or pd.isna(cfi) or pd.isna(cff):
            continue

        pattern = capital_allocation_pattern(cfo, cfi, cff)
        rows.append(
            {
                "company_id": r["company_id"],
                "year": r["year"],
                "cfo_sign": "+" if cfo >= 0 else "-",
                "cfi_sign": "+" if cfi >= 0 else "-",
                "cff_sign": "+" if cff >= 0 else "-",
                "pattern_label": pattern,
            }
        )

    return pd.DataFrame(
        rows, columns=["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"]
    )


def generate_capital_allocation_table(db_path=DEFAULT_DB_PATH, output_path=DEFAULT_OUTPUT_PATH):
    """Build and write output/capital_allocation.csv. Returns (path, n_rows)."""
    df = build_capital_allocation_table(db_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path, len(df)


if __name__ == "__main__":
    path, n = generate_capital_allocation_table()
    print(f"Wrote {path} ({n} company-year rows)")
