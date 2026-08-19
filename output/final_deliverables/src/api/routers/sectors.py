"""
sectors.py
----------
Sector list (with median KPIs) and per-sector company membership.
"""

import statistics

from fastapi import APIRouter, Depends, HTTPException

from src.api.db import get_db_connection

router = APIRouter(prefix="/sectors", tags=["sectors"])


def _median(values):
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return statistics.median(clean)


@router.get("")
def list_sectors(conn=Depends(get_db_connection)):
    """All broad sectors with company_count, median_roe, median_pe, median_de."""
    sectors = conn.execute("""
        SELECT broad_sector, COUNT(*) AS company_count
        FROM sectors
        GROUP BY broad_sector
        ORDER BY company_count DESC
        """).fetchall()

    result = []
    for row in sectors:
        broad_sector = row["broad_sector"]

        roe_rows = conn.execute(
            """
            SELECT c.roe_percentage
            FROM companies c
            JOIN sectors s ON s.company_id = c.company_id
            WHERE s.broad_sector = ?
            """,
            (broad_sector,),
        ).fetchall()

        pe_de_rows = conn.execute(
            """
            SELECT fr.debt_to_equity, mc.pe_ratio
            FROM sectors s
            LEFT JOIN (
                SELECT company_id, debt_to_equity
                FROM financial_ratios
                WHERE (company_id, year) IN (
                    SELECT company_id, MAX(year) FROM financial_ratios GROUP BY company_id
                )
            ) fr ON fr.company_id = s.company_id
            LEFT JOIN (
                SELECT company_id, pe_ratio
                FROM market_cap
                WHERE (company_id, year) IN (
                    SELECT company_id, MAX(year) FROM market_cap GROUP BY company_id
                )
            ) mc ON mc.company_id = s.company_id
            WHERE s.broad_sector = ?
            """,
            (broad_sector,),
        ).fetchall()

        result.append(
            {
                "broad_sector": broad_sector,
                "company_count": row["company_count"],
                "median_roe": _median([r["roe_percentage"] for r in roe_rows]),
                "median_pe": _median([r["pe_ratio"] for r in pe_de_rows]),
                "median_de": _median([r["debt_to_equity"] for r in pe_de_rows]),
            }
        )

    return result


@router.get("/{broad_sector}/companies")
def companies_in_sector(broad_sector: str, conn=Depends(get_db_connection)):
    """All companies in a sector, with latest-year KPIs. 404 for an unknown sector."""
    exists = conn.execute(
        "SELECT 1 FROM sectors WHERE broad_sector = ? LIMIT 1", (broad_sector,)
    ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"Unknown sector '{broad_sector}'")

    rows = conn.execute(
        """
        SELECT
            c.company_id, c.company_name, c.roe_percentage, c.roce_percentage,
            s.sub_sector, s.market_cap_category
        FROM sectors s
        JOIN companies c ON c.company_id = s.company_id
        WHERE s.broad_sector = ?
        ORDER BY c.company_name
        """,
        (broad_sector,),
    ).fetchall()
    return [dict(row) for row in rows]
