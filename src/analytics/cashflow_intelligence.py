"""
src/analytics/cashflow_intelligence.py
-----------------------------------------
Module 7 - Cash Flow Intelligence (Section 10 of the project spec).
Deliverable D-13 (output/cashflow_intelligence.xlsx) and the
Section 16 risk-register-adjacent distress alert list
(output/distress_alerts.csv).

Like `capital_allocation.csv` (see `src/analytics/capital_allocation.py`),
`cashflow_intelligence.xlsx` existed in `output/` as a static file with
no generator anywhere in `src/` - only `src/reports/tearsheet.py` read
from it. This module is the missing generator, built from the existing
pure formula functions in `src/analytics/cashflow_kpis.py` and
`src/analytics/cagr.py` so every number here is traceable back to a
formula and a source column, per the spec's "no black-box numbers"
principle (Section 8, Mission & Objectives Matrix).

Methodology (one row per company, using each company's cash flow /
P&L history in `nifty100.db`):

  cfo_quality_score / cfo_quality_label (7.1)
      Mean of the annual CFO/PAT ratio over each company's most recent
      up-to-5 fiscal years (years with PAT <= 0 are excluded, since the
      ratio is not meaningful there). Labelled with the same >1.0 /
      >=0.5 / else thresholds as `cfo_quality_score()`.

  capex_intensity_pct / capex_label (7.2)
      abs(investing_activity) / sales x 100 for the latest available
      year, labelled Asset Light (<3%) / Moderate (<=8%) / Capital
      Intensive (>8%) via `capex_intensity()`.

  fcf_cagr_5yr (7.3)
      FCF CAGR over the most recent 5-year window available, using
      `calculate_cagr()`'s turnaround / zero-base edge-case rules
      (i.e. None where the base year FCF is <= 0, exactly as the
      Revenue/PAT/EPS CAGR engine already behaves elsewhere).

  fcf_conversion_pct (7.4)
      FCF / operating_profit x 100 for the latest year, via
      `fcf_conversion()`.

  deleveraging_flag (7.5)
      CFF < 0 in the latest year AND borrowings declined vs. the prior
      year on record.

  distress_flag (7.6)
      CFO < 0 AND CFF > 0 in the latest year.

  capital_allocation_label (7.7)
      Latest-year pattern label from `output/capital_allocation.csv`
      (see `src/analytics/capital_allocation.py`), so the label shown
      here always matches the Module 2 capital-allocation table rather
      than being computed twice with two chances to drift apart.

Run with:
    PYTHONPATH=. python3 src/analytics/cashflow_intelligence.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cagr import calculate_cagr
from src.analytics.cashflow_kpis import capex_intensity, fcf_conversion, free_cash_flow

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
CAPITAL_ALLOCATION_CSV = PROJECT_ROOT / "output" / "capital_allocation.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "cashflow_intelligence.xlsx"
DEFAULT_DISTRESS_PATH = PROJECT_ROOT / "output" / "distress_alerts.csv"


def _cfo_quality(history):
    """5yr-avg CFO/PAT ratio -> (score, label). None/'' if no usable years."""
    recent = history.tail(5)
    ratios = [
        row.operating_activity / row.net_profit
        for row in recent.itertuples()
        if pd.notna(row.operating_activity) and pd.notna(row.net_profit) and row.net_profit > 0
    ]
    if not ratios:
        return None, None

    score = sum(ratios) / len(ratios)
    if score > 1:
        label = "High Quality"
    elif score >= 0.5:
        label = "Moderate"
    else:
        label = "Accrual Risk"
    return round(score, 2), label


def _fcf_cagr_5yr(history):
    """FCF CAGR over the widest available <=5yr window."""
    fcf_hist = history.dropna(subset=["operating_activity", "investing_activity"]).copy()
    if len(fcf_hist) < 2:
        return None
    fcf_hist["fcf"] = fcf_hist["operating_activity"] + fcf_hist["investing_activity"]

    end_row = fcf_hist.iloc[-1]
    window = fcf_hist[fcf_hist["year"] <= end_row["year"] - 1]
    window = window[window["year"] >= end_row["year"] - 5]
    if window.empty:
        return None
    start_row = window.iloc[0]

    n_years = end_row["year"] - start_row["year"]
    cagr, _flag = calculate_cagr(start_row["fcf"], end_row["fcf"], n_years)
    return round(cagr, 2) if cagr is not None else None


def build_cashflow_intelligence_table(db_path=DEFAULT_DB_PATH):
    """Compute one Module 7 summary row per company. Returns a DataFrame."""
    conn = sqlite3.connect(db_path)
    cf = pd.read_sql(
        "SELECT company_id, year, operating_activity, investing_activity, "
        "financing_activity FROM cashflow WHERE year IS NOT NULL ORDER BY company_id, year",
        conn,
    )
    pnl = pd.read_sql(
        "SELECT company_id, year, sales, operating_profit, net_profit FROM profitandloss "
        "WHERE year IS NOT NULL ORDER BY company_id, year",
        conn,
    )
    bs = pd.read_sql(
        "SELECT company_id, year, borrowings FROM balancesheet WHERE year IS NOT NULL "
        "ORDER BY company_id, year",
        conn,
    )
    sectors = pd.read_sql("SELECT company_id, broad_sector AS sector FROM sectors", conn)
    all_companies = pd.read_sql("SELECT company_id FROM companies", conn)["company_id"].tolist()
    conn.close()

    cap_alloc = (
        pd.read_csv(CAPITAL_ALLOCATION_CSV) if CAPITAL_ALLOCATION_CSV.exists() else pd.DataFrame()
    )

    hist = cf.merge(pnl, on=["company_id", "year"], how="left")

    rows = []
    covered = set()
    for company_id, g in hist.groupby("company_id"):
        covered.add(company_id)
        g = g.sort_values("year")
        latest = g.iloc[-1]

        cfo_score, cfo_label = _cfo_quality(g)

        capex_pct, capex_label = (None, None)
        if pd.notna(latest["sales"]) and latest["sales"] > 0:
            result = capex_intensity(latest["investing_activity"], latest["sales"])
            if result is not None:
                capex_pct, capex_label = round(result[0], 2), result[1]

        fcf_cagr = _fcf_cagr_5yr(g)

        fcf_conv = None
        if pd.notna(latest["operating_profit"]) and latest["operating_profit"] != 0:
            latest_fcf = free_cash_flow(latest["operating_activity"], latest["investing_activity"])
            fcf_conv = round(fcf_conversion(latest_fcf, latest["operating_profit"]), 2)

        company_bs = bs[bs.company_id == company_id].sort_values("year")
        deleveraging = False
        if len(company_bs) >= 2 and latest["financing_activity"] < 0:
            deleveraging = bool(
                company_bs.iloc[-1]["borrowings"] < company_bs.iloc[-2]["borrowings"]
            )

        distress = bool(latest["operating_activity"] < 0 and latest["financing_activity"] > 0)

        cap_label = None
        if not cap_alloc.empty:
            co_alloc = cap_alloc[cap_alloc.company_id == company_id].dropna(subset=["year"])
            if not co_alloc.empty:
                cap_label = co_alloc.sort_values("year").iloc[-1]["pattern_label"]

        sector_row = sectors[sectors.company_id == company_id]
        sector = sector_row.iloc[0]["sector"] if not sector_row.empty else None

        rows.append(
            {
                "company_id": company_id,
                "sector": sector,
                "cfo_quality_score": cfo_score,
                "cfo_quality_label": cfo_label,
                "capex_intensity_pct": capex_pct,
                "capex_label": capex_label,
                "fcf_cagr_5yr": fcf_cagr,
                "fcf_conversion_pct": fcf_conv,
                "distress_flag": distress,
                "deleveraging_flag": deleveraging,
                "capital_allocation_label": cap_label,
            }
        )

    # Companies with zero cashflow-table history (e.g. ATGL - see Section 16
    # Risk Register R-01) can't have any cash-flow-derived metric computed,
    # but should still appear in the deliverable with a sector and nulls
    # elsewhere, rather than silently vanishing from a 92-company summary.
    for company_id in set(all_companies) - covered:
        sector_row = sectors[sectors.company_id == company_id]
        rows.append(
            {
                "company_id": company_id,
                "sector": sector_row.iloc[0]["sector"] if not sector_row.empty else None,
                "cfo_quality_score": None,
                "cfo_quality_label": None,
                "capex_intensity_pct": None,
                "capex_label": None,
                "fcf_cagr_5yr": None,
                "fcf_conversion_pct": None,
                "distress_flag": False,
                "deleveraging_flag": False,
                "capital_allocation_label": None,
            }
        )

    return pd.DataFrame(rows).sort_values("company_id").reset_index(drop=True)


def generate_cashflow_intelligence_outputs(
    db_path=DEFAULT_DB_PATH,
    output_path=DEFAULT_OUTPUT_PATH,
    distress_path=DEFAULT_DISTRESS_PATH,
):
    """Write cashflow_intelligence.xlsx and distress_alerts.csv. Returns (paths, n_flagged)."""
    df = build_cashflow_intelligence_table(db_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)

    distress = df[df["distress_flag"]][
        ["company_id", "sector", "cfo_quality_label", "capital_allocation_label"]
    ]
    distress.to_csv(distress_path, index=False)

    return (output_path, distress_path), len(distress)


if __name__ == "__main__":
    (out_path, alerts_path), n_flagged = generate_cashflow_intelligence_outputs()
    print(f"Wrote {out_path} ({len(build_cashflow_intelligence_table())} companies)")
    print(f"Wrote {alerts_path} ({n_flagged} flagged)")
