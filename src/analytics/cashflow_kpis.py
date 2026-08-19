def free_cash_flow(operating_activity, investing_activity):
    """
    FCF = CFO + CFI
    """
    return operating_activity + investing_activity


def cfo_quality_score(cfo, pat):
    """
    CFO / PAT Quality Score
    """

    if pat == 0:
        return None

    ratio = cfo / pat

    if ratio > 1:
        return "High Quality"

    if ratio >= 0.5:
        return "Moderate"

    return "Accrual Risk"


def capex_intensity(investing_activity, sales):
    """
    CapEx Intensity
    """

    if sales <= 0:
        return None

    capex = abs(investing_activity) / sales * 100

    if capex < 3:
        label = "Asset Light"

    elif capex <= 8:
        label = "Moderate"

    else:
        label = "Capital Intensive"

    return capex, label


def fcf_conversion(fcf, operating_profit):
    """Fcf conversion."""
    if operating_profit == 0:
        return None

    return (fcf / operating_profit) * 100


def capital_allocation_pattern(cfo, cfi, cff):
    """Capital allocation pattern."""
    signs = ("+" if cfo >= 0 else "-", "+" if cfi >= 0 else "-", "+" if cff >= 0 else "-")

    mapping = {
        ("+", "-", "-"): "Reinvestor",
        ("+", "+", "-"): "Liquidating Assets",
        ("-", "+", "+"): "Distress Signal",
        ("-", "-", "+"): "Growth Funded by Debt",
        ("+", "+", "+"): "Cash Accumulator",
        ("-", "-", "-"): "Pre-Revenue",
        ("+", "-", "+"): "Mixed",
    }

    return mapping.get(signs, "Unknown")
