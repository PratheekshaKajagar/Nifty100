"""
src/etl/backfill_financial_ratios.py
-------------------------------------
Fixes a data-completeness gap left over from an earlier sprint: the
supplementary `financial_ratios.xlsx` source (Section 6.4 of the
project spec) was pre-computed against the full 100-ticker Nifty 100
universe *before* the 92-company data-availability filter was applied,
so it carries ratio rows for two tickers that are not in the 92-company
`companies` master (ULTRACEMCO, UNIONBANK) while being completely
missing two companies that *are* in the master and do have raw
financial-statement history (ATGL, SBIN).

Because Module 3 (Screener), Module 4 (Peer Comparison), Module 10
(Clustering) and the dashboard's Screener/Peer/Capital-Allocation
screens all read from `financial_ratios` with an INNER JOIN
(`src/screener/engine.py::load_screener_data`), any company entirely
absent from `financial_ratios` silently disappears from every one of
those modules. That was the root cause of the AC-04 (row count) and
AC-15 (cluster coverage) acceptance-gate failures.

This script closes the gap the way Module 2 (the Ratio Engine) was
specified to work in the first place: it computes the missing
company-years directly from the raw P&L / Balance Sheet / Cash Flow
statements using the existing pure ratio functions in
`src/analytics/ratios.py` and `src/analytics/cashflow_kpis.py`, rather
than trusting the static pre-supplied spreadsheet as ground truth.
Ratios that need a statement the company doesn't have for a given year
(e.g. ATGL has no Cash Flow history, SBIN has no Balance Sheet history)
are correctly left as NULL/None, exactly as the Ratio Engine's own
edge-case rules already do for every other company (see Section 13 of
the spec, "Edge Case / Warning Flag" column).

Run with:
    PYTHONPATH=. python3 src/etl/backfill_financial_ratios.py

Writes the corrected table back to data/processed/financial_ratios.csv
(and, since Appendix A marks financial_ratios.xlsx as "Computed —
regenerate from DB", to data/raw/financial_ratios.xlsx as well) so the
fix is picked up automatically the next time
`src/etl/load_to_sqlite.py` rebuilds nifty100.db - no manual DB
patching required.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.cashflow_kpis import free_cash_flow
from src.analytics.ratios import (
    asset_turnover,
    debt_to_equity,
    interest_coverage,
    net_profit_margin,
    operating_profit_margin,
    roe,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

FR_COLUMNS = [
    "id",
    "company_id",
    "year",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "capex_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "total_debt_cr",
    "cash_from_operations_cr",
]


def _nan_to_none(value):
    """Coerce pandas/numpy NaN to a real Python None for clean formula edge cases."""
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def compute_missing_rows(companies, pnl, bs, cf, existing_fr):
    """
    Return a DataFrame of financial_ratios rows for every
    (company_id, year) that is in `companies` + has a valid-year P&L
    record, but is not already present in `existing_fr`.
    """
    valid_ids = set(companies["company_id"].astype(str).str.strip().str.upper())

    pnl = pnl.copy()
    pnl["company_id"] = pnl["company_id"].astype(str).str.strip().str.upper()
    pnl = pnl[pnl["company_id"].isin(valid_ids) & pnl["year"].notna()]
    pnl["year"] = pnl["year"].astype(int)

    existing_keys = set(
        zip(
            existing_fr["company_id"].astype(str).str.strip().str.upper(),
            existing_fr["year"].astype(int),
        )
    )

    missing = pnl[~pnl.apply(lambda r: (r["company_id"], r["year"]) in existing_keys, axis=1)]

    if missing.empty:
        return pd.DataFrame(columns=FR_COLUMNS)

    bs = bs.copy()
    bs["company_id"] = bs["company_id"].astype(str).str.strip().str.upper()
    bs = bs.dropna(subset=["year"])
    bs["year"] = bs["year"].astype(int)

    cf = cf.copy()
    cf["company_id"] = cf["company_id"].astype(str).str.strip().str.upper()
    cf = cf.dropna(subset=["year"])
    cf["year"] = cf["year"].astype(int)

    comp = companies.copy()
    comp["company_id"] = comp["company_id"].astype(str).str.strip().str.upper()

    merged = (
        missing.merge(bs, on=["company_id", "year"], how="left", suffixes=("", "_bs"))
        .merge(cf, on=["company_id", "year"], how="left", suffixes=("", "_cf"))
        .merge(comp[["company_id", "face_value"]], on="company_id", how="left")
    )

    next_id = int(existing_fr["id"].max()) + 1 if len(existing_fr) else 1
    rows = []

    for _, r in merged.iterrows():
        has_bs = pd.notna(r.get("equity_capital"))
        has_cf = pd.notna(r.get("operating_activity"))

        net_profit = _nan_to_none(r.get("net_profit"))
        sales = _nan_to_none(r.get("sales"))
        op_profit = _nan_to_none(r.get("operating_profit"))
        other_income = _nan_to_none(r.get("other_income"))
        interest = _nan_to_none(r.get("interest"))

        equity_capital = _nan_to_none(r.get("equity_capital")) if has_bs else None
        reserves = _nan_to_none(r.get("reserves")) if has_bs else None
        borrowings = _nan_to_none(r.get("borrowings")) if has_bs else None
        total_assets = _nan_to_none(r.get("total_assets")) if has_bs else None
        face_value = _nan_to_none(r.get("face_value"))

        operating_activity = _nan_to_none(r.get("operating_activity")) if has_cf else None
        investing_activity = _nan_to_none(r.get("investing_activity")) if has_cf else None

        npm = (
            net_profit_margin(net_profit, sales)
            if net_profit is not None and sales is not None
            else None
        )
        opm = (
            operating_profit_margin(op_profit, sales)
            if op_profit is not None and sales is not None
            else None
        )
        roe_val = (
            roe(net_profit, equity_capital, reserves) if has_bs and net_profit is not None else None
        )
        de_val = debt_to_equity(borrowings, equity_capital, reserves) if has_bs else None
        icr_val = (
            interest_coverage(op_profit, other_income or 0, interest)
            if interest is not None and op_profit is not None
            else None
        )
        at_val = asset_turnover(sales, total_assets) if has_bs and sales is not None else None
        fcf_val = free_cash_flow(operating_activity, investing_activity) if has_cf else None
        capex_val = abs(investing_activity) if has_cf and investing_activity is not None else None
        bvps_val = (
            (equity_capital + reserves) / (equity_capital / face_value)
            if has_bs and face_value not in (None, 0) and equity_capital not in (None, 0)
            else None
        )

        rows.append(
            {
                "id": next_id,
                "company_id": r["company_id"],
                "year": int(r["year"]),
                "net_profit_margin_pct": npm,
                "operating_profit_margin_pct": opm,
                "return_on_equity_pct": roe_val,
                "debt_to_equity": de_val,
                "interest_coverage": icr_val,
                "asset_turnover": at_val,
                "free_cash_flow_cr": fcf_val,
                "capex_cr": capex_val,
                "earnings_per_share": _nan_to_none(r.get("eps")),
                "book_value_per_share": bvps_val,
                "dividend_payout_ratio_pct": _nan_to_none(r.get("dividend_payout")),
                "total_debt_cr": borrowings,
                "cash_from_operations_cr": operating_activity,
            }
        )
        next_id += 1

    return pd.DataFrame(rows, columns=FR_COLUMNS)


def run_backfill():
    """Load processed sources, compute missing rows, write the corrected table back out."""
    companies = pd.read_csv(PROCESSED_DIR / "companies.csv")
    pnl = pd.read_csv(PROCESSED_DIR / "profitandloss.csv")
    bs = pd.read_csv(PROCESSED_DIR / "balancesheet.csv")
    cf = pd.read_csv(PROCESSED_DIR / "cashflow.csv")
    existing_fr = pd.read_csv(PROCESSED_DIR / "financial_ratios.csv")

    new_rows = compute_missing_rows(companies, pnl, bs, cf, existing_fr)

    if new_rows.empty:
        print("No missing financial_ratios rows found - nothing to backfill.")
        return existing_fr

    combined = pd.concat([existing_fr, new_rows], ignore_index=True)
    combined = combined.sort_values(["company_id", "year"]).reset_index(drop=True)

    combined.to_csv(PROCESSED_DIR / "financial_ratios.csv", index=False)
    combined.to_excel(RAW_DIR / "financial_ratios.xlsx", index=False)

    print(
        f"Backfilled {len(new_rows)} financial_ratios row(s) for "
        f"{sorted(new_rows['company_id'].unique())}."
    )
    print(f"financial_ratios: {len(existing_fr)} -> {len(combined)} rows.")
    return combined


if __name__ == "__main__":
    run_backfill()
