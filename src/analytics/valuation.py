"""
valuation.py
------------
FCF yield + relative-valuation flagging for every company, using
market_cap history.

  FCF yield %       = free_cash_flow_cr / market_cap_crore * 100
  5yr median PE     = median of the company's own PE over its last 5 years
  sector median PE  = median PE across the company's broad_sector, latest year
  flag:
    Caution  if PE > sector_median_PE * 1.5
    Discount if PE < sector_median_PE * 0.7
    Fair     otherwise
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "output" / "valuation_summary.xlsx"
DEFAULT_FLAGS_PATH = PROJECT_ROOT / "output" / "valuation_flags.csv"


def _load_latest_market_data(conn):
    query = """
        SELECT mc.company_id, mc.year, mc.market_cap_crore, mc.pe_ratio,
               mc.pb_ratio, mc.ev_ebitda, mc.dividend_yield_pct
        FROM market_cap mc
        ORDER BY mc.company_id, mc.year
    """
    return pd.read_sql(query, conn)


def compute_valuation_table(db_path):
    """
    Returns a DataFrame with one row per company:
      company_id, company_name, sector, pe_ratio, pb_ratio, ev_ebitda,
      fcf_yield_pct, five_yr_median_pe, sector_median_pe,
      pe_vs_sector_median_pct, flag
    """
    conn = sqlite3.connect(db_path)

    market_history = _load_latest_market_data(conn)

    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    fcf_latest = pd.read_sql(
        """
        SELECT company_id, year, free_cash_flow_cr
        FROM financial_ratios
        WHERE year IS NOT NULL
        """,
        conn,
    )

    conn.close()

    # ---- latest-year market snapshot per company ----
    latest_market = (
        market_history.dropna(subset=["year"])
        .sort_values("year")
        .groupby("company_id", as_index=False)
        .last()
    )

    # ---- 5yr median PE per company ----
    five_yr_median = []
    for company_id, group in market_history.dropna(subset=["year"]).groupby("company_id"):
        group = group.sort_values("year")
        last5 = group.tail(5)
        five_yr_median.append(
            {
                "company_id": company_id,
                "five_yr_median_pe": last5["pe_ratio"].median(),
            }
        )
    five_yr_median = pd.DataFrame(five_yr_median)

    # ---- latest FCF per company ----
    latest_fcf = (
        fcf_latest.dropna(subset=["year"])
        .sort_values("year")
        .groupby("company_id", as_index=False)
        .last()[["company_id", "free_cash_flow_cr"]]
    )

    df = (
        latest_market.merge(companies, on="company_id", how="left")
        .merge(sectors, on="company_id", how="left")
        .merge(five_yr_median, on="company_id", how="left")
        .merge(latest_fcf, on="company_id", how="left")
    )

    # ---- FCF yield ----
    df["fcf_yield_pct"] = np.where(
        (df["market_cap_crore"].notna()) & (df["market_cap_crore"] != 0),
        df["free_cash_flow_cr"] / df["market_cap_crore"] * 100,
        np.nan,
    )

    # ---- sector median PE, computed in the latest year available per sector ----
    sector_median_pe = (
        df.groupby("broad_sector")["pe_ratio"].median().rename("sector_median_pe").reset_index()
    )
    df = df.merge(sector_median_pe, on="broad_sector", how="left")

    df["pe_vs_sector_median_pct"] = np.where(
        (df["sector_median_pe"].notna()) & (df["sector_median_pe"] != 0),
        (df["pe_ratio"] / df["sector_median_pe"] - 1) * 100,
        np.nan,
    )

    def _flag(row):
        pe = row["pe_ratio"]
        median = row["sector_median_pe"]
        if pd.isna(pe) or pd.isna(median) or median == 0:
            return "Fair"
        if pe > median * 1.5:
            return "Caution"
        if pe < median * 0.7:
            return "Discount"
        return "Fair"

    df["flag"] = df.apply(_flag, axis=1)

    df = df.rename(
        columns={
            "broad_sector": "sector",
            "pe_ratio": "P/E",
            "pb_ratio": "P/B",
            "ev_ebitda": "EV/EBITDA",
            "five_yr_median_pe": "5yr_median_PE",
        }
    )

    return df[
        [
            "company_id",
            "company_name",
            "sector",
            "P/E",
            "P/B",
            "EV/EBITDA",
            "fcf_yield_pct",
            "5yr_median_PE",
            "pe_vs_sector_median_pct",
            "flag",
        ]
    ]


def _autosize_and_style(ws, df):
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    flag_fills = {
        "Caution": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
        "Discount": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
        "Fair": PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid"),
    }

    for col_idx, col_name in enumerate(df.columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.fill = header_fill
        cell.font = header_font

    flag_col_idx = list(df.columns).index("flag") + 1

    for row_idx, row in enumerate(df.itertuples(index=False), start=2):
        row_dict = row._asdict()
        for col_idx, col_name in enumerate(df.columns, start=1):
            value = row_dict.get(col_name)
            if isinstance(value, float) and value != value:
                value = None
            ws.cell(row=row_idx, column=col_idx, value=value)

        fill = flag_fills.get(row_dict.get("flag"))
        if fill:
            ws.cell(row=row_idx, column=flag_col_idx).fill = fill

    for col_idx, col_name in enumerate(df.columns, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(
            14, len(str(col_name)) + 2
        )

    ws.freeze_panes = "A2"


def generate_valuation_outputs(db_path, summary_path=None, flags_path=None):
    """Generate valuation outputs."""
    summary_path = Path(summary_path) if summary_path else DEFAULT_SUMMARY_PATH
    flags_path = Path(flags_path) if flags_path else DEFAULT_FLAGS_PATH
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    flags_path.parent.mkdir(parents=True, exist_ok=True)

    df = compute_valuation_table(db_path)

    wb = Workbook()
    ws = wb.active
    ws.title = "Valuation Summary"
    _autosize_and_style(ws, df)
    wb.save(summary_path)

    flagged = df[df["flag"].isin(["Caution", "Discount"])].sort_values(
        by="pe_vs_sector_median_pct", ascending=False
    )
    flagged.to_csv(flags_path, index=False)

    return summary_path, flags_path, len(df), len(flagged)


if __name__ == "__main__":
    summary, flags, n_total, n_flagged = generate_valuation_outputs(
        PROJECT_ROOT / "data" / "nifty100.db"
    )
    print(f"Wrote {summary} ({n_total} companies)")
    print(f"Wrote {flags} ({n_flagged} flagged)")
