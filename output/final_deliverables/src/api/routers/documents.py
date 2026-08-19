"""
documents.py
------------
Annual report document links, per company/year.
"""

from fastapi import APIRouter, Depends, HTTPException

from src.api.db import get_db_connection

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{company_id}")
def company_documents(company_id: str, conn=Depends(get_db_connection)):
    """Company documents."""
    rows = conn.execute(
        """
        SELECT year, annual_report
        FROM documents
        WHERE company_id = ?
        ORDER BY year DESC
        """,
        (company_id,),
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No documents found for '{company_id}'")

    return [dict(row) for row in rows]
