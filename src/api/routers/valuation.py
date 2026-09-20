"""
valuation.py
------------
Market cap / valuation multiples, sourced from the `market_cap` table.
"""

from fastapi import APIRouter, Depends, HTTPException

from src.api.db import get_db_connection

router = APIRouter(prefix="/valuation", tags=["valuation"])


@router.get("/{company_id}")
def valuation_history(company_id: str, conn=Depends(get_db_connection)):
    """Valuation history."""
    rows = conn.execute(
        """
        SELECT year, market_cap_crore, enterprise_value_crore,
               pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
        FROM market_cap
        WHERE company_id = ?
        ORDER BY year
        """,
        (company_id,),
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No valuation data for '{company_id}'")

    return [dict(row) for row in rows]


@router.get("/{company_id}/latest")
def valuation_latest(company_id: str, conn=Depends(get_db_connection)):
    """Valuation latest."""
    row = conn.execute(
        """
        SELECT year, market_cap_crore, enterprise_value_crore,
               pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
        FROM market_cap
        WHERE company_id = ?
        ORDER BY year DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"No valuation data for '{company_id}'")

    return dict(row)
