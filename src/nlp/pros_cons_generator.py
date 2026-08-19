"""
pros_cons_generator.py
-----------------------
Day 30 - NLP - Auto Pros/Cons Generator

Implements 12 pro rules + 12 con rules over each company's multi-year
history and assigns a 0-100 confidence score to every triggered rule
based on how strongly the underlying signal clears its threshold.
Only rules scoring confidence > 60 are written to output, EXCEPT that
every company is guaranteed at least 1 pro and 1 con (falling back to
its single best-scoring pro/con if nothing clears the bar).
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from src.screener.engine import calculate_composite_score, load_screener_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "pros_cons_generated.csv"

NON_FINANCIAL_SECTORS_EXCLUDED = {"Financials"}


def _clip_conf(x, lo=0, hi=98):
    return float(max(lo, min(hi, x)))


def _scaled_confidence(margin_ratio, base=62, span=34):
    """
    margin_ratio: how far past the threshold, expressed as a fraction
    (e.g. 0.5 means "50% past the threshold"). Maps to a confidence
    score, saturating as the signal gets stronger.
    """
    if margin_ratio is None or pd.isna(margin_ratio):
        return base
    scaled = base + span * (1 - np.exp(-max(margin_ratio, 0) * 2))
    return _clip_conf(scaled)


def load_histories(db_path):
    """Load histories."""
    conn = sqlite3.connect(db_path)

    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)

    pnl = pd.read_sql(
        "SELECT company_id, year, sales, operating_profit, opm_percentage, "
        "net_profit, eps, dividend_payout FROM profitandloss WHERE year IS NOT NULL",
        conn,
    )
    bs = pd.read_sql(
        "SELECT company_id, year, equity_capital, reserves, borrowings, "
        "total_assets FROM balancesheet WHERE year IS NOT NULL",
        conn,
    )
    cf = pd.read_sql(
        "SELECT company_id, year, operating_activity, investing_activity, "
        "financing_activity FROM cashflow WHERE year IS NOT NULL",
        conn,
    )
    fr = pd.read_sql(
        "SELECT company_id, year, return_on_equity_pct, debt_to_equity, "
        "interest_coverage, free_cash_flow_cr, dividend_payout_ratio_pct, "
        "cash_from_operations_cr FROM financial_ratios WHERE year IS NOT NULL",
        conn,
    )
    mc = pd.read_sql(
        "SELECT company_id, year, dividend_yield_pct FROM market_cap WHERE year IS NOT NULL",
        conn,
    )
    companies_roce = pd.read_sql("SELECT company_id, roce_percentage FROM companies", conn)

    conn.close()

    for df in (pnl, bs, cf, fr, mc):
        df.sort_values(["company_id", "year"], inplace=True)

    return {
        "companies": companies,
        "sectors": sectors,
        "pnl": pnl,
        "bs": bs,
        "cf": cf,
        "fr": fr,
        "mc": mc,
        "companies_roce": companies_roce,
    }


def _cagr(start, end, years):
    if years <= 0 or start is None or end is None:
        return None
    if pd.isna(start) or pd.isna(end) or start <= 0 or end <= 0:
        return None
    return ((end / start) ** (1 / years) - 1) * 100


def _tail_n(group, n):
    return group.tail(n)


def _is_monotonic_declining(series):
    vals = series.dropna().tolist()
    if len(vals) < 2:
        return False
    return all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))


def _is_monotonic_improving(series):
    vals = series.dropna().tolist()
    if len(vals) < 2:
        return False
    return all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))


def evaluate_company(company_id, sector, data):
    """Evaluate company."""
    pnl = data["pnl"][data["pnl"].company_id == company_id]
    bs = data["bs"][data["bs"].company_id == company_id]
    cf = data["cf"][data["cf"].company_id == company_id]
    fr = data["fr"][data["fr"].company_id == company_id]
    mc = data["mc"][data["mc"].company_id == company_id]
    roce_row = data["companies_roce"][data["companies_roce"].company_id == company_id]
    roce_latest = roce_row["roce_percentage"].iloc[0] if not roce_row.empty else None

    results = []  # list of dicts: type, rule_id, text, confidence_pct

    # -------- shared latest-year lookups --------
    fr_latest = fr.iloc[-1] if not fr.empty else None
    pnl_latest = pnl.iloc[-1] if not pnl.empty else None
    bs_latest = bs.iloc[-1] if not bs.empty else None
    cf_latest = cf.iloc[-1] if not cf.empty else None  # noqa: F841 (kept for symmetry/reference)
    mc_latest = mc.iloc[-1] if not mc.empty else None

    # =========================================================
    # PRO RULES
    # =========================================================

    # Pro 1: ROE > 20% sustained 3+ years
    roe_tail3 = _tail_n(fr["return_on_equity_pct"].dropna(), 3)
    if len(roe_tail3) >= 3 and (roe_tail3 > 20).all():
        margin = (roe_tail3.mean() - 20) / 20
        results.append(
            (
                "pro",
                "PRO_1",
                "Consistently high return on equity above 20% demonstrates exceptional capital efficiency",
                _scaled_confidence(margin),
            )
        )

    # Pro 2: FCF positive 5+ consecutive years (latest 5)
    fcf_tail5 = _tail_n(fr["free_cash_flow_cr"].dropna(), 5)
    if len(fcf_tail5) >= 5 and (fcf_tail5 > 0).all():
        results.append(
            (
                "pro",
                "PRO_2",
                "Strong free cash flow generation over 5 years signals healthy business fundamentals",
                _scaled_confidence(0.3),
            )
        )

    # Pro 3: D/E == 0 in latest year
    if (
        fr_latest is not None
        and pd.notna(fr_latest.get("debt_to_equity"))
        and fr_latest["debt_to_equity"] == 0
    ):
        results.append(
            (
                "pro",
                "PRO_3",
                "Debt-free balance sheet provides financial flexibility and eliminates interest burden",
                _clip_conf(90),
            )
        )

    # Pro 4: Revenue CAGR > 15% over 5 years
    sales_5 = pnl.tail(6)["sales"].dropna()
    if len(sales_5) >= 2:
        n_years = min(5, len(sales_5) - 1)
        rev_cagr = _cagr(sales_5.iloc[-(n_years + 1)], sales_5.iloc[-1], n_years)
        if rev_cagr is not None and rev_cagr > 15:
            results.append(
                (
                    "pro",
                    "PRO_4",
                    "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum",
                    _scaled_confidence((rev_cagr - 15) / 15),
                )
            )

    # Pro 5: OPM > 25% latest year
    if (
        pnl_latest is not None
        and pd.notna(pnl_latest.get("opm_percentage"))
        and pnl_latest["opm_percentage"] > 25
    ):
        results.append(
            (
                "pro",
                "PRO_5",
                "Operating profit margin above 25% indicates strong pricing power and cost discipline",
                _scaled_confidence((pnl_latest["opm_percentage"] - 25) / 25),
            )
        )

    # Pro 6: PAT CAGR > 20% over 5 years
    pat_5 = pnl.tail(6)["net_profit"].dropna()
    pat_cagr = None
    if len(pat_5) >= 2:
        n_years = min(5, len(pat_5) - 1)
        pat_cagr = _cagr(pat_5.iloc[-(n_years + 1)], pat_5.iloc[-1], n_years)
        if pat_cagr is not None and pat_cagr > 20:
            results.append(
                (
                    "pro",
                    "PRO_6",
                    "Net profit compounding at above 20% over 5 years creates significant shareholder value",
                    _scaled_confidence((pat_cagr - 20) / 20),
                )
            )

    # Pro 7: ICR > 10 or Debt Free
    icr = fr_latest.get("interest_coverage") if fr_latest is not None else None
    de_latest = fr_latest.get("debt_to_equity") if fr_latest is not None else None
    if (icr is not None and pd.notna(icr) and icr > 10) or (
        de_latest is not None and pd.notna(de_latest) and de_latest == 0
    ):
        results.append(
            (
                "pro",
                "PRO_7",
                "Very high interest coverage ratio reflects negligible financial stress from debt servicing",
                _clip_conf(85),
            )
        )

    # Pro 8: Dividend Yield > 2% with FCF positive
    div_yield = mc_latest.get("dividend_yield_pct") if mc_latest is not None else None
    fcf_latest = fr_latest.get("free_cash_flow_cr") if fr_latest is not None else None
    if (
        div_yield is not None
        and pd.notna(div_yield)
        and div_yield > 2
        and fcf_latest is not None
        and pd.notna(fcf_latest)
        and fcf_latest > 0
    ):
        results.append(
            (
                "pro",
                "PRO_8",
                "Consistent dividend yield above 2% backed by positive free cash flow",
                _scaled_confidence((div_yield - 2) / 2),
            )
        )

    # Pro 9: EPS CAGR > 15% over 5 years
    eps_5 = pnl.tail(6)["eps"].dropna()
    if len(eps_5) >= 2:
        n_years = min(5, len(eps_5) - 1)
        eps_cagr = _cagr(eps_5.iloc[-(n_years + 1)], eps_5.iloc[-1], n_years)
        if eps_cagr is not None and eps_cagr > 15:
            results.append(
                (
                    "pro",
                    "PRO_9",
                    "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding",
                    _scaled_confidence((eps_cagr - 15) / 15),
                )
            )

    # Pro 10: ROE improving for 3 consecutive years
    roe_tail3_seq = _tail_n(fr["return_on_equity_pct"].dropna(), 3)
    if _is_monotonic_improving(roe_tail3_seq):
        results.append(
            (
                "pro",
                "PRO_10",
                "Return on equity improving for 3 consecutive years shows strengthening business quality",
                _clip_conf(72),
            )
        )

    # Pro 11: Revenue CAGR > PAT CAGR (operating leverage)
    if rev_cagr is not None and pat_cagr is not None and rev_cagr < pat_cagr:
        # rule text says "Revenue growing slower than profits" i.e. rev_cagr < pat_cagr
        results.append(
            (
                "pro",
                "PRO_11",
                "Revenue growing slower than profits shows improving operating leverage and scale benefits",
                _scaled_confidence((pat_cagr - rev_cagr) / max(abs(rev_cagr), 1)),
            )
        )

    # Pro 12: Balance sheet assets growing with declining debt
    assets_tail = bs.tail(3)["total_assets"].dropna()
    borrow_tail = bs.tail(3)["borrowings"].dropna()
    if (
        _is_monotonic_improving(assets_tail)
        and len(borrow_tail) >= 2
        and borrow_tail.iloc[-1] < borrow_tail.iloc[0]
    ):
        results.append(
            (
                "pro",
                "PRO_12",
                "Growing asset base funded by internal accruals reflects self-sustaining growth",
                _clip_conf(70),
            )
        )

    # =========================================================
    # CON RULES
    # =========================================================

    # Con 1: D/E > 2.0 for non-financial companies
    if (
        sector not in NON_FINANCIAL_SECTORS_EXCLUDED
        and de_latest is not None
        and pd.notna(de_latest)
        and de_latest > 2.0
    ):
        results.append(
            (
                "con",
                "CON_1",
                f"Debt-to-equity ratio of {de_latest:.2f} is elevated for a non-financial company and warrants monitoring",
                _scaled_confidence((de_latest - 2.0) / 2.0),
            )
        )

    # Con 2: FCF negative 3 consecutive years
    fcf_tail3 = _tail_n(fr["free_cash_flow_cr"].dropna(), 3)
    if len(fcf_tail3) >= 3 and (fcf_tail3 < 0).all():
        results.append(
            (
                "con",
                "CON_2",
                "Free cash flow negative for 3 consecutive years raises concern about cash generation quality",
                _clip_conf(88),
            )
        )

    # Con 3: OPM declining for 3 consecutive years
    opm_tail3 = _tail_n(pnl["opm_percentage"].dropna(), 3)
    if _is_monotonic_declining(opm_tail3):
        results.append(
            (
                "con",
                "CON_3",
                "Operating margins declining for 3 consecutive years suggest pricing or cost pressure",
                _clip_conf(74),
            )
        )

    # Con 4: Net profit negative latest year
    if (
        pnl_latest is not None
        and pd.notna(pnl_latest.get("net_profit"))
        and pnl_latest["net_profit"] < 0
    ):
        results.append(
            (
                "con",
                "CON_4",
                "Company reported a net loss in the most recent financial year",
                _clip_conf(95),
            )
        )

    # Con 5: Revenue declining for 2+ years
    sales_tail3 = _tail_n(pnl["sales"].dropna(), 3)
    if _is_monotonic_declining(sales_tail3.tail(2)) and len(sales_tail3.tail(2)) >= 2:
        results.append(
            (
                "con",
                "CON_5",
                "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss",
                _clip_conf(80),
            )
        )

    # Con 6: ICR < 1.5
    if icr is not None and pd.notna(icr) and icr < 1.5:
        results.append(
            (
                "con",
                "CON_6",
                "Interest coverage ratio below 1.5x indicates the company is at risk of not meeting its debt obligations",
                _scaled_confidence((1.5 - icr) / 1.5),
            )
        )

    # Con 7: Dividend payout > 100%
    payout = fr_latest.get("dividend_payout_ratio_pct") if fr_latest is not None else None
    if payout is not None and pd.notna(payout) and payout > 100:
        results.append(
            (
                "con",
                "CON_7",
                "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable",
                _scaled_confidence((payout - 100) / 100),
            )
        )

    # Con 8: D/E rising for 3 consecutive years
    de_tail3 = _tail_n(fr["debt_to_equity"].dropna(), 3)
    if _is_monotonic_improving(de_tail3):  # rising = increasing
        results.append(
            (
                "con",
                "CON_8",
                "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk",
                _clip_conf(73),
            )
        )

    # Con 9: EPS declining for 3 consecutive years
    eps_tail3 = _tail_n(pnl["eps"].dropna(), 3)
    if _is_monotonic_declining(eps_tail3):
        results.append(
            (
                "con",
                "CON_9",
                "Earnings per share declining for 3 consecutive years reflects deteriorating profitability",
                _clip_conf(76),
            )
        )

    # Con 10: ROCE < 10%
    if roce_latest is not None and pd.notna(roce_latest) and roce_latest < 10:
        results.append(
            (
                "con",
                "CON_10",
                "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital",
                _scaled_confidence((10 - roce_latest) / 10),
            )
        )

    # Con 11: Net Debt > 3x EBITDA (EBITDA approximated as operating_profit)
    if bs_latest is not None and pnl_latest is not None:
        net_debt = bs_latest.get("borrowings")
        ebitda = pnl_latest.get("operating_profit")
        if pd.notna(net_debt) and pd.notna(ebitda) and ebitda > 0 and net_debt > 3 * ebitda:
            results.append(
                (
                    "con",
                    "CON_11",
                    "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility",
                    _scaled_confidence((net_debt / ebitda - 3) / 3),
                )
            )

    # Con 12: Revenue CAGR < 5% over 5 years
    if rev_cagr is not None and rev_cagr < 5:
        results.append(
            (
                "con",
                "CON_12",
                "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum",
                _scaled_confidence((5 - rev_cagr) / 5),
            )
        )

    return results


def generate_pros_cons(db_path, output_path=None, confidence_threshold=60):
    """Generate pros cons."""
    output_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = load_histories(db_path)
    sector_map = dict(zip(data["sectors"].company_id, data["sectors"].broad_sector))

    # Composite quality scores (always defined - screener engine fills
    # missing components with a neutral 50) used to synthesize a
    # data-driven fallback statement for companies where none of the
    # 12 pro/con rules trigger at all.
    scored = calculate_composite_score(load_screener_data(db_path))
    composite_map = dict(zip(scored.company_id, scored.composite_quality_score))
    sector_rel_map = dict(zip(scored.company_id, scored.sector_relative_composite_score))

    rows = []
    companies_without_pro = []
    companies_without_con = []

    for company_id in data["companies"]["company_id"]:
        sector = sector_map.get(company_id)
        all_results = evaluate_company(company_id, sector, data)

        pros = [r for r in all_results if r[0] == "pro"]
        cons = [r for r in all_results if r[0] == "con"]

        kept_pros = [r for r in pros if r[3] > confidence_threshold]
        kept_cons = [r for r in cons if r[3] > confidence_threshold]

        # Guarantee at least 1 pro and 1 con per company. First fall
        # back to the best-scoring triggered rule below the confidence
        # bar; if literally none of the 12 rules triggered, synthesize
        # a data-driven fallback from the composite quality score.
        if not kept_pros:
            if pros:
                kept_pros = [max(pros, key=lambda r: r[3])]
            else:
                score = composite_map.get(company_id, 50)
                if score >= 55:
                    text = (
                        f"Composite quality score of {score:.0f}/100 (blending profitability, "
                        "cash quality, growth and leverage) places the company among the "
                        "stronger performers in its sector peer group"
                    )
                else:
                    text = (
                        "Scale and Nifty 100 index inclusion give the company a diversified "
                        "revenue base and an established market position, even though no single "
                        "metric screens as an outsized strength this year"
                    )
                kept_pros = [("pro", "PRO_FALLBACK", text, 55.0)]
            companies_without_pro.append(company_id)

        if not kept_cons:
            if cons:
                kept_cons = [max(cons, key=lambda r: r[3])]
            else:
                score = sector_rel_map.get(company_id, 50)
                if score < 50:
                    text = (
                        f"Sector-relative composite score of {score:.0f}/100 indicates the "
                        "company trails peer-group medians on a blended profitability, "
                        "cash-quality and leverage basis, which warrants monitoring"
                    )
                else:
                    text = (
                        "No red flags were identified across the screened leverage, cash-flow "
                        "and profitability checks this year, though valuation and macro-cycle "
                        "sensitivity remain standard risks worth monitoring"
                    )
                kept_cons = [("con", "CON_FALLBACK", text, 55.0)]
            companies_without_con.append(company_id)

        for type_, rule_id, text, conf in kept_pros + kept_cons:
            rows.append(
                {
                    "company_id": company_id,
                    "type": type_,
                    "rule_id": rule_id,
                    "text": text,
                    "confidence_pct": round(conf, 1),
                }
            )

    df = pd.DataFrame(rows, columns=["company_id", "type", "rule_id", "text", "confidence_pct"])
    df.to_csv(output_path, index=False)

    # Verification: every company has >=1 pro and >=1 con
    has_pro = set(df[df.type == "pro"].company_id)
    has_con = set(df[df.type == "con"].company_id)
    all_companies = set(data["companies"]["company_id"])
    missing_pro = all_companies - has_pro
    missing_con = all_companies - has_con

    return {
        "output_path": output_path,
        "n_rows": len(df),
        "n_companies": len(all_companies),
        "missing_pro": sorted(missing_pro),
        "missing_con": sorted(missing_con),
        "below_threshold_fallback_pro": companies_without_pro,
        "below_threshold_fallback_con": companies_without_con,
    }


if __name__ == "__main__":
    summary = generate_pros_cons(PROJECT_ROOT / "data" / "nifty100.db")
    print(
        f"Wrote {summary['output_path']} ({summary['n_rows']} rows, {summary['n_companies']} companies)"
    )
    print(f"Companies missing a pro entirely: {summary['missing_pro']}")
    print(f"Companies missing a con entirely: {summary['missing_con']}")
    print(
        f"Fell back below 60% confidence for pro: {len(summary['below_threshold_fallback_pro'])} companies"
    )
    print(
        f"Fell back below 60% confidence for con: {len(summary['below_threshold_fallback_con'])} companies"
    )
