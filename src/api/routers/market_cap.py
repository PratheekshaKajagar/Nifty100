"""
market_cap.py
--------------
Day 40 spec-exact route: GET /api/v1/market-cap/{ticker} - historical
valuation multiples (P/E, P/B, EV/EBITDA, dividend yield) from 2019
to 2024. This is the same underlying `market_cap` table already
served (with an extra endpoint or two) by valuation.py under
/api/v1/valuation/{company_id} - kept as its own tiny router purely
so the literal path the spec calls out also exists.
"""

from fastapi import APIRouter, Depends, HTTPException

from src.api.db import get_db_connection

router = APIRouter(prefix="/market-cap", tags=["market-cap"])


@router.get("/{ticker}")
def market_cap_history(
    ticker: str,
    from_year: int = 2019,
    to_year: int = 2024,
    conn=Depends(get_db_connection),
):
    """Historical valuation multiples (P/E, P/B, EV/EBITDA, dividend yield) for a ticker."""
    exists = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (ticker,)).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    rows = conn.execute(
        """
        SELECT year, market_cap_crore, enterprise_value_crore,
               pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
        FROM market_cap
        WHERE company_id = ? AND year BETWEEN ? AND ?
        ORDER BY year
        """,
        (ticker, from_year, to_year),
    ).fetchall()

    return {
        "company_id": ticker,
        "from_year": from_year,
        "to_year": to_year,
        "history": [dict(row) for row in rows],
    }
