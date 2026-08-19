"""
capital_allocation_report.py
-----------------------------
Day 32 - Capital Allocation Report

- Verifies output/capital_allocation.csv (from Sprint 2) coverage
- Builds a distribution summary: count of companies per pattern,
  latest year
- Detects year-over-year pattern changes -> output/pattern_changes.csv
"""

import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAPITAL_ALLOCATION_CSV = PROJECT_ROOT / "output" / "capital_allocation.csv"
DEFAULT_PATTERN_CHANGES_PATH = PROJECT_ROOT / "output" / "pattern_changes.csv"

ALL_PATTERNS = [
    "Reinvestor",
    "Liquidating Assets",
    "Distress Signal",
    "Growth Funded by Debt",
    "Cash Accumulator",
    "Pre-Revenue",
    "Mixed",
    "Unknown",
]


def verify_capital_allocation_coverage(db_path):
    """Returns a dict summarising coverage of capital_allocation.csv
    against the full companies x years universe."""
    conn = sqlite3.connect(db_path)
    all_companies = set(pd.read_sql("SELECT company_id FROM companies", conn)["company_id"])
    conn.close()

    df = pd.read_csv(CAPITAL_ALLOCATION_CSV)
    covered_companies = set(df["company_id"].unique())
    missing_companies = sorted(all_companies - covered_companies)

    return {
        "n_companies_total": len(all_companies),
        "n_companies_covered": len(covered_companies),
        "missing_companies": missing_companies,
        "n_rows": len(df),
    }


def distribution_summary_latest_year(df):
    """Count of companies in each of the 8 capital-allocation patterns
    for their latest available year."""
    df = df.dropna(subset=["year"]).copy()
    latest = df.sort_values("year").groupby("company_id", as_index=False).last()

    counts = latest["pattern_label"].value_counts().reindex(ALL_PATTERNS, fill_value=0)
    summary = counts.rename_axis("pattern_label").reset_index(name="company_count")
    return summary, latest


def detect_pattern_changes(df):
    """For each company, compares the pattern in its latest year vs.
    the year before it and flags a change (e.g. Reinvestor -> Distress
    Signal)."""
    df = df.dropna(subset=["year"]).copy()
    df.sort_values(["company_id", "year"], inplace=True)

    records = []
    for company_id, group in df.groupby("company_id"):
        if len(group) < 2:
            continue
        prev_row = group.iloc[-2]
        latest_row = group.iloc[-1]
        if prev_row["pattern_label"] != latest_row["pattern_label"]:
            records.append(
                {
                    "company_id": company_id,
                    "prev_year": int(prev_row["year"]),
                    "prev_pattern": prev_row["pattern_label"],
                    "latest_year": int(latest_row["year"]),
                    "latest_pattern": latest_row["pattern_label"],
                }
            )

    return pd.DataFrame(
        records,
        columns=["company_id", "prev_year", "prev_pattern", "latest_year", "latest_pattern"],
    )


def generate_capital_allocation_report(db_path, pattern_changes_path=None):
    """Generate capital allocation report."""
    pattern_changes_path = (
        Path(pattern_changes_path) if pattern_changes_path else DEFAULT_PATTERN_CHANGES_PATH
    )
    pattern_changes_path.parent.mkdir(parents=True, exist_ok=True)

    coverage = verify_capital_allocation_coverage(db_path)

    df = pd.read_csv(CAPITAL_ALLOCATION_CSV)
    dist_summary, latest = distribution_summary_latest_year(df)
    pattern_changes = detect_pattern_changes(df)
    pattern_changes.to_csv(pattern_changes_path, index=False)

    return coverage, dist_summary, pattern_changes, pattern_changes_path


if __name__ == "__main__":
    coverage, dist_summary, pattern_changes, path = generate_capital_allocation_report(
        PROJECT_ROOT / "data" / "nifty100.db"
    )
    print("Coverage:", coverage)
    print()
    print("Latest-year pattern distribution:")
    print(dist_summary.to_string(index=False))
    print()
    print(f"Wrote {path} ({len(pattern_changes)} companies changed pattern YoY)")
