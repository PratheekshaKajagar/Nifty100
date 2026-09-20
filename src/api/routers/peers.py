"""
peers.py
--------
Peer group membership and the peer_percentiles rankings computed by
src/analytics/peer.py.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException

from src.api.db import get_db_connection

router = APIRouter(prefix="/peers", tags=["peers"])


@router.get("/groups")
def list_peer_groups(conn=Depends(get_db_connection)):
    """List peer groups."""
    rows = conn.execute("""
        SELECT peer_group_name, COUNT(*) AS member_count
        FROM peer_groups
        GROUP BY peer_group_name
        ORDER BY peer_group_name
        """).fetchall()
    return [dict(row) for row in rows]


@router.get("/groups/{peer_group_name}")
def peer_group_members(peer_group_name: str, conn=Depends(get_db_connection)):
    """Peer group members."""
    rows = conn.execute(
        "SELECT company_id, is_benchmark FROM peer_groups WHERE peer_group_name = ?",
        (peer_group_name,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.get("/{company_id}/percentiles")
def company_peer_percentiles(company_id: str, conn=Depends(get_db_connection)):
    """Company peer percentiles."""
    rows = conn.execute(
        """
        SELECT peer_group_name, metric, value, percentile_rank, year
        FROM peer_percentiles
        WHERE company_id = ?
        ORDER BY peer_group_name, metric
        """,
        (company_id,),
    ).fetchall()
    return [dict(row) for row in rows]


# ----------------------------------------------------
# GET /api/v1/peers/{group_name}
# Day 40 spec-exact route: all companies in a peer group, each with
# their percentile rank for every metric tracked in peer_percentiles
# (10 metrics - see src/analytics/peer.py).
# ----------------------------------------------------
@router.get("/{group_name}")
def peer_group_detail(group_name: str, conn=Depends(get_db_connection)):
    """Peer group detail."""
    members = conn.execute(
        "SELECT company_id, is_benchmark FROM peer_groups WHERE peer_group_name = ?",
        (group_name,),
    ).fetchall()

    if not members:
        raise HTTPException(status_code=404, detail=f"Unknown peer group '{group_name}'")

    percentile_rows = conn.execute(
        """
        SELECT company_id, metric, value, percentile_rank, year
        FROM peer_percentiles
        WHERE peer_group_name = ?
        ORDER BY company_id, metric
        """,
        (group_name,),
    ).fetchall()

    by_company = defaultdict(dict)
    for row in percentile_rows:
        by_company[row["company_id"]][row["metric"]] = {
            "value": row["value"],
            "percentile_rank": row["percentile_rank"],
            "year": row["year"],
        }

    companies = [
        {
            "company_id": m["company_id"],
            "is_benchmark": bool(m["is_benchmark"]),
            "metrics": by_company.get(m["company_id"], {}),
        }
        for m in members
    ]

    return {
        "peer_group_name": group_name,
        "member_count": len(companies),
        "companies": companies,
    }
