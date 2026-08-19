def calculate_cagr(start_value, end_value, years):
    """
    CAGR = ((End / Start) ** (1 / Years) - 1) * 100
    """

    if years <= 0:
        return None, "INVALID_PERIOD"

    if start_value == 0:
        return None, "ZERO_BASE"

    if start_value > 0 and end_value > 0:
        cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
        return cagr, "NORMAL"

    if start_value > 0 and end_value < 0:
        return None, "DECLINE_TO_LOSS"

    if start_value < 0 and end_value > 0:
        return None, "TURNAROUND"

    if start_value < 0 and end_value < 0:
        return None, "BOTH_NEGATIVE"

    return None, "UNKNOWN"


def revenue_cagr(start, end, years):
    """Revenue cagr."""
    return calculate_cagr(start, end, years)


def pat_cagr(start, end, years):
    """Pat cagr."""
    return calculate_cagr(start, end, years)


def eps_cagr(start, end, years):
    """Eps cagr."""
    return calculate_cagr(start, end, years)
