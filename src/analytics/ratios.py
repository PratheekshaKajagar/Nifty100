def net_profit_margin(net_profit, sales):
    """Net profit margin."""
    if sales is None or sales <= 0:
        return None
    return (net_profit / sales) * 100


def operating_profit_margin(operating_profit, sales):
    """Operating profit margin."""
    if sales is None or sales <= 0:
        return None
    return (operating_profit / sales) * 100


def opm_cross_check(calculated_opm, source_opm):
    """Opm cross check."""
    if calculated_opm is None or source_opm is None:
        return False

    return abs(calculated_opm - source_opm) > 1


def roe(net_profit, equity_capital, reserves):
    """Roe."""
    equity = equity_capital + reserves

    if equity <= 0:
        return None

    return (net_profit / equity) * 100


def roce(ebit, equity_capital, reserves, borrowings):
    """Roce."""
    capital = equity_capital + reserves + borrowings

    if capital <= 0:
        return None

    return (ebit / capital) * 100


def roa(net_profit, total_assets):
    """Roa."""
    if total_assets <= 0:
        return None

    return (net_profit / total_assets) * 100


# ----------------------------------------------------
# Day 09 - Leverage & Efficiency Ratios
# ----------------------------------------------------


def debt_to_equity(borrowings, equity_capital, reserves):
    """
    Debt / Equity
    """

    equity = equity_capital + reserves

    if borrowings == 0:
        return 0

    if equity <= 0:
        return None

    return borrowings / equity


def high_leverage_flag(de_ratio, sector):
    """High leverage flag."""
    if de_ratio is None:
        return False

    if sector is None:
        return False

    sector = str(sector).strip().lower()

    financial_sectors = ["financials", "bank", "banks", "nbfc", "insurance"]

    if sector in financial_sectors:
        return False

    return de_ratio > 5


def interest_coverage(operating_profit, other_income, interest):
    """Interest coverage."""
    if interest == 0:
        return None

    return (operating_profit + other_income) / interest


def icr_label(icr):
    """Icr label."""
    if icr is None:
        return "Debt Free"

    return ""


def icr_warning(icr):
    """Icr warning."""
    if icr is None:
        return False

    return icr < 1.5


def net_debt(borrowings, investments):
    """Net debt."""
    return borrowings - investments


def asset_turnover(sales, total_assets):
    """Asset turnover."""
    if total_assets <= 0:
        return None

    return sales / total_assets
