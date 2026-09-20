"""
parser.py
---------
Day 29 - NLP - Analysis Text Parser

Parses the free-text period/value fields in the `analysis` table
(compounded_sales_growth, compounded_profit_growth, stock_price_cagr, roe)
using a regex, and cross-validates the parsed CAGR values against CAGR
computed by the Ratio Engine (src.screener.engine).

NOTE ON COVERAGE: the `analysis` table only has rows for 4 companies
(HDFCBANK, INFY, SBILIFE, TCS) - this is a known data-foundation
limitation, not a bug in this parser. Every row present is parsed;
entries that don't match the pattern are logged to parse_failures.csv.
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.screener.engine import load_screener_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "analysis_parsed.csv"
DEFAULT_FAILURES_PATH = PROJECT_ROOT / "output" / "parse_failures.csv"

# (\d+) period, optional "Years"/"Year", optional colon, value%
PATTERN = re.compile(r"(\d+)\s*Years?:?\s*([\d.]+)%")

METRIC_COLUMNS = {
    "compounded_sales_growth": "compounded_sales_growth",
    "compounded_profit_growth": "compounded_profit_growth",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}

# Which parsed metric+period maps to which Ratio-Engine 5yr CAGR column,
# for cross-validation (only the 5-year entries are directly comparable).
CROSS_VALIDATE_MAP = {
    ("compounded_sales_growth", 5): "compounded_sales_growth",
    ("compounded_profit_growth", 5): "compounded_profit_growth",
}


def _load_raw_analysis(conn):
    return pd.read_sql(
        "SELECT id, company_id, compounded_sales_growth, "
        "compounded_profit_growth, stock_price_cagr, roe FROM analysis",
        conn,
    )


def parse_analysis_table(db_path):
    """
    Returns (parsed_df, failures_df).

    parsed_df columns: company_id, metric_type, period_years, value_pct
    failures_df columns: company_id, metric_type, raw_text
    """
    conn = sqlite3.connect(db_path)
    raw = _load_raw_analysis(conn)
    conn.close()

    parsed_records = []
    failure_records = []

    for _, row in raw.iterrows():
        company_id = row["company_id"]
        for metric_type in METRIC_COLUMNS:
            text = row[metric_type]
            if text is None or (isinstance(text, float) and pd.isna(text)):
                continue
            text = str(text)
            match = PATTERN.search(text)
            if match:
                period_years = int(match.group(1))
                value_pct = float(match.group(2))
                parsed_records.append(
                    {
                        "company_id": company_id,
                        "metric_type": metric_type,
                        "period_years": period_years,
                        "value_pct": value_pct,
                    }
                )
            else:
                failure_records.append(
                    {
                        "company_id": company_id,
                        "metric_type": metric_type,
                        "raw_text": text,
                    }
                )

    parsed_df = pd.DataFrame(
        parsed_records,
        columns=["company_id", "metric_type", "period_years", "value_pct"],
    )
    failures_df = pd.DataFrame(
        failure_records,
        columns=["company_id", "metric_type", "raw_text"],
    )

    return parsed_df, failures_df


def cross_validate(parsed_df, db_path, tolerance_pct=5.0):
    """
    Adds computed_cagr_pct, divergence_pct, flag_for_review columns to
    parsed_df wherever a comparable Ratio-Engine 5yr CAGR exists.
    """
    computed = load_screener_data(db_path)[
        ["company_id", "compounded_sales_growth", "compounded_profit_growth"]
    ].rename(
        columns={
            "compounded_sales_growth": "computed_compounded_sales_growth",
            "compounded_profit_growth": "computed_compounded_profit_growth",
        }
    )

    df = parsed_df.merge(computed, on="company_id", how="left")

    def _computed_value(row):
        if row["period_years"] != 5:
            return None
        if row["metric_type"] == "compounded_sales_growth":
            return row["computed_compounded_sales_growth"]
        if row["metric_type"] == "compounded_profit_growth":
            return row["computed_compounded_profit_growth"]
        return None

    df["computed_cagr_pct"] = df.apply(_computed_value, axis=1)

    df["divergence_pct"] = (df["value_pct"] - df["computed_cagr_pct"]).abs()
    df["flag_for_review"] = df["divergence_pct"] > tolerance_pct

    df = df.drop(columns=["computed_compounded_sales_growth", "computed_compounded_profit_growth"])

    return df


def generate_parsed_outputs(db_path, output_path=None, failures_path=None):
    """Generate parsed outputs."""
    output_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    failures_path = Path(failures_path) if failures_path else DEFAULT_FAILURES_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failures_path.parent.mkdir(parents=True, exist_ok=True)

    parsed_df, failures_df = parse_analysis_table(db_path)
    parsed_df = cross_validate(parsed_df, db_path)

    parsed_df.to_csv(output_path, index=False)
    failures_df.to_csv(failures_path, index=False)

    n_flagged = int(parsed_df["flag_for_review"].sum())

    return output_path, failures_path, len(parsed_df), len(failures_df), n_flagged


if __name__ == "__main__":
    out, fail, n_parsed, n_fail, n_flag = generate_parsed_outputs(
        PROJECT_ROOT / "data" / "nifty100.db"
    )
    print(f"Wrote {out} ({n_parsed} rows parsed)")
    print(f"Wrote {fail} ({n_fail} unmatched entries)")
    print(f"{n_flag} rows flagged for review (>5% divergence vs Ratio Engine)")
