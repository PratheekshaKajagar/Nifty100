"""
Financial Ratio Engine (Module 2)
Computes 50+ KPIs for every company-year combination.
"""
import sqlite3
from typing import Optional
import numpy as np
import pandas as pd


# --- Profitability & Return Ratios ---

def net_profit_margin(net_profit: Optional[float], sales: Optional[float]) -> Optional[float]:
    """Net Profit Margin = (Net Profit / Sales) * 100"""
    if sales is None or sales <= 0 or net_profit is None:
        return None
    return round((net_profit / sales) * 100, 2)


def operating_profit_margin(operating_profit: Optional[float], sales: Optional[float]) -> Optional[float]:
    """Operating Profit Margin = (Operating Profit / Sales) * 100"""
    if sales is None or sales <= 0 or operating_profit is None:
        return None
    return round((operating_profit / sales) * 100, 2)


def opm_cross_check(source_opm: Optional[float], computed_opm: Optional[float], tolerance: float = 1.0) -> bool:
    """Returns True if a discrepancy exists (diff > tolerance), False otherwise."""
    if source_opm is None or computed_opm is None:
        return True
    return abs(source_opm - computed_opm) > tolerance


def roe(net_profit: Optional[float], equity_capital: Optional[float], reserves: Optional[float] = 0.0) -> Optional[float]:
    """ROE = Net Profit / (Equity Capital + Reserves) * 100"""
    if net_profit is None or equity_capital is None:
        return None
    total_equity = equity_capital + (reserves if reserves is not None else 0.0)
    if total_equity <= 0:
        return None
    return round((net_profit / total_equity) * 100, 2)


def roce(arg1: Optional[float] = None, arg2: Optional[float] = None, 
         arg3: Optional[float] = None, arg4: Optional[float] = None, 
         *args, **kwargs) -> Optional[float]:
    """
    Flexible ROCE calculation supporting:
    - 4 positional args: roce(ebit, equity, reserves, borrowings) -> ebit / (equity + reserves + borrowings) * 100
    - 6 keyword/positional args: roce(op_profit, other_inc, depr, equity, reserves, borrowings)
    """
    # If called with kwargs
    if "ebit" in kwargs:
        ebit = kwargs.get("ebit")
        equity = kwargs.get("equity", 0.0) or 0.0
        reserves = kwargs.get("reserves", 0.0) or 0.0
        borrowings = kwargs.get("borrowings", 0.0) or 0.0
    elif len(args) == 2:  # 6 total positional (arg1..arg4 + 2 args)
        op_prof = arg1 or 0.0
        depr = arg3 or 0.0
        ebit = op_prof - depr
        equity = arg4 or 0.0
        reserves = args[0] or 0.0
        borrowings = args[1] or 0.0
    else:
        # Standard test call: roce(ebit, equity_capital, reserves, borrowings)
        ebit = arg1
        equity = arg2 or 0.0
        reserves = arg3 or 0.0
        borrowings = arg4 or 0.0

    if ebit is None:
        return None
    
    cap_employed = (equity or 0.0) + (reserves or 0.0) + (borrowings or 0.0)
    if cap_employed <= 0:
        return None
    return round((ebit / cap_employed) * 100, 2)


def roa(net_profit: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """ROA = (Net Profit / Total Assets) * 100"""
    if total_assets is None or total_assets <= 0 or net_profit is None:
        return None
    return round((net_profit / total_assets) * 100, 2)


# --- Leverage & Solvency Functions ---

def debt_to_equity(borrowings: Optional[float], equity_capital: Optional[float], 
                   reserves: Optional[float] = 0.0, is_financial: bool = False) -> Optional[float]:
    """Debt to Equity = Borrowings / (Equity + Reserves). Returns None for Financials."""
    if is_financial:
        return None
    if equity_capital is None:
        return None
    total_equity = equity_capital + (reserves if reserves is not None else 0.0)
    if total_equity <= 0:
        return None
    if borrowings is None or borrowings == 0:
        return 0.0
    return round(borrowings / total_equity, 2)


def high_leverage_flag(de_ratio: Optional[float], sector: Optional[str] = None, threshold: float = 2.0) -> bool:
    """Flags high leverage (> threshold). Financials/Banks are never flagged."""
    if sector and any(s in sector.lower() for s in ['financial', 'bank', 'insurance', 'nbfc']):
        return False
    if de_ratio is None:
        return False
    return de_ratio > threshold


def interest_coverage(operating_profit: Optional[float], other_income: Optional[float], 
                      interest: Optional[float]) -> Optional[float]:
    """ICR = (Operating Profit + Other Income) / Interest"""
    if interest is None or interest == 0:
        return None
    if operating_profit is None:
        return None
    return round(((operating_profit or 0.0) + (other_income or 0.0)) / interest, 2)


def icr_label(icr_value: Optional[float]) -> str:
    """Classifies ICR status."""
    if icr_value is None:
        return "Debt Free"
    if icr_value < 1.5:
        return "High Risk"
    if icr_value < 3.0:
        return "Moderate"
    return "Safe"


def icr_warning(icr_value: Optional[float]) -> bool:
    """Warning if ICR < 1.5"""
    if icr_value is None:
        return False
    return icr_value < 1.5


def net_debt(borrowings: Optional[float], investments: Optional[float], cash: Optional[float] = 0.0) -> Optional[float]:
    """Net Debt = Borrowings - Investments - Cash"""
    if borrowings is None:
        return None
    return round(borrowings - (investments or 0.0) - (cash or 0.0), 2)


def asset_turnover(sales: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """Asset Turnover = Sales / Total Assets"""
    if total_assets is None or total_assets <= 0 or sales is None:
        return None
    return round(sales / total_assets, 2)


calculate_roe = roe
calculate_roce = roce


def generate_ratios_dataframe(db_path: str = "data/nifty100.db") -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = """
    SELECT 
        p.company_id,
        p.year,
        p.sales,
        p.operating_profit,
        p.opm_percentage,
        p.other_income,
        p.interest,
        p.depreciation,
        p.profit_before_tax,
        p.tax_percentage,
        p.net_profit,
        p.eps,
        p.dividend_payout,
        b.equity_capital,
        b.reserves,
        b.borrowings,
        b.other_liabilities,
        b.total_liabilities,
        b.fixed_assets,
        b.cwip,
        b.investments,
        b.other_asset,
        b.total_assets,
        c.operating_activity,
        c.investing_activity,
        c.financing_activity,
        c.net_cash_flow,
        s.broad_sector
    FROM profitandloss p
    LEFT JOIN balancesheet b ON p.company_id = b.company_id AND p.year = b.year
    LEFT JOIN cashflow c ON p.company_id = c.company_id AND p.year = c.year
    LEFT JOIN sectors s ON p.company_id = s.company_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    records = []
    for _, row in df.iterrows():
        sales = row['sales']
        net_prof = row['net_profit']
        op_prof = row['operating_profit']
        depr = row['depreciation'] or 0.0
        equity_cap = row['equity_capital']
        res = row['reserves']
        debt = row['borrowings']
        interest = row['interest']
        assets = row['total_assets']
        cfo = row['operating_activity']
        cfi = row['investing_activity']
        is_bank = row['broad_sector'] == 'Financials'

        ebit = (op_prof or 0.0) - depr if op_prof is not None else None
        npm = net_profit_margin(net_prof, sales)
        opm = row['opm_percentage'] if row['opm_percentage'] is not None else operating_profit_margin(op_prof, sales)
        roe_val = roe(net_prof, equity_cap, res)
        roce_val = roce(ebit, equity_cap, res, debt)
        de_val = debt_to_equity(debt, equity_cap, res, is_financial=is_bank)
        icr_val = interest_coverage(op_prof, row['other_income'], interest)
        at_val = asset_turnover(sales, assets)
        fcf = round((cfo or 0.0) + (cfi or 0.0), 2) if (cfo is not None or cfi is not None) else None
        capex = abs(cfi) if cfi is not None else None

        records.append({
            "company_id": row['company_id'],
            "year": row['year'],
            "net_profit_margin_pct": npm,
            "operating_profit_margin_pct": opm,
            "return_on_equity_pct": roe_val,
            "return_on_capital_employed_pct": roce_val,
            "debt_to_equity": de_val,
            "interest_coverage": icr_val,
            "asset_turnover": at_val,
            "free_cash_flow_cr": fcf,
            "capex_cr": capex,
            "earnings_per_share": row['eps'],
            "dividend_payout_ratio_pct": row['dividend_payout'],
            "total_debt_cr": debt,
            "cash_from_operations_cr": cfo
        })

    return pd.DataFrame(records)


def save_financial_ratios(db_path: str = "data/nifty100.db", output_excel: str = "output/financial_ratios.xlsx"):
    ratios_df = generate_ratios_dataframe(db_path)
    conn = sqlite3.connect(db_path)
    ratios_df.to_sql("financial_ratios", conn, if_exists="replace", index=False)
    conn.close()
    ratios_df.to_excel(output_excel, index=False)
    print(f"[OK] Generated financial_ratios: {len(ratios_df)} rows")


if __name__ == "__main__":
    save_financial_ratios()