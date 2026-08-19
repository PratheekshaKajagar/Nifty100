"""
Companies API Router (Module 11)
Endpoints for company profiles, statements, and ratios.
"""
import os
import sqlite3
from typing import Optional, List, Dict, Any, Union
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from src.api.db import get_db_connection

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("")
def list_companies(
    sector: Optional[str] = None, 
    market_cap_category: Optional[str] = None,
    search: Optional[str] = None,
    q: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List all companies with optional filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT c.id, c.company_name, s.broad_sector, s.sub_sector, s.market_cap_category 
    FROM companies c 
    LEFT JOIN sectors s ON c.id = s.company_id
    WHERE 1=1
    """
    params = []
    
    if sector:
        query += " AND (s.broad_sector = ? OR s.broad_sector LIKE ?)"
        params.extend([sector, f"%{sector}%"])
    if market_cap_category:
        query += " AND s.market_cap_category = ?"
        params.append(market_cap_category)
    search_term = search or q
    if search_term:
        query += " AND (c.id LIKE ? OR c.company_name LIKE ?)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])
        
    query += " ORDER BY c.id ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


@router.get("/{ticker}/tearsheet")
def download_tearsheet(ticker: str):
    """Download company PDF tearsheet."""
    ticker = ticker.strip().upper()
    pdf_paths = [
        f"reports/tearsheets/{ticker}_tearsheet.pdf",
        f"output/final_deliverables/reports/tearsheets/{ticker}_tearsheet.pdf"
    ]
    for p in pdf_paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="application/pdf", filename=f"{ticker}_tearsheet.pdf")
    raise HTTPException(status_code=404, detail=f"Tearsheet for {ticker} not found")


@router.get("/{ticker}/pl")
def get_company_pl(
    ticker: str, 
    from_year: Optional[str] = None, 
    to_year: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get Profit and Loss history for a company."""
    ticker = ticker.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM profitandloss WHERE company_id = ?"
    params = [ticker]
    
    if from_year:
        query += " AND year >= ?"
        params.append(str(from_year))
    if to_year:
        query += " AND year <= ?"
        params.append(str(to_year))
        
    query += " ORDER BY year ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail=f"P&L data for {ticker} not found")
        
    return [dict(row) for row in rows]


@router.get("/{ticker}/bs")
def get_company_bs(
    ticker: str, 
    from_year: Optional[str] = None, 
    to_year: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get Balance Sheet history for a company."""
    ticker = ticker.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM balancesheet WHERE company_id = ?"
    params = [ticker]
    
    if from_year:
        query += " AND year >= ?"
        params.append(str(from_year))
    if to_year:
        query += " AND year <= ?"
        params.append(str(to_year))
        
    query += " ORDER BY year ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail=f"Balance sheet for {ticker} not found")
        
    return [dict(row) for row in rows]


@router.get("/{ticker}/cashflow")
def get_company_cashflow(
    ticker: str, 
    from_year: Optional[str] = None, 
    to_year: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get Cash Flow history for a company."""
    ticker = ticker.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM cashflow WHERE company_id = ?"
    params = [ticker]
    
    if from_year:
        query += " AND year >= ?"
        params.append(str(from_year))
    if to_year:
        query += " AND year <= ?"
        params.append(str(to_year))
        
    query += " ORDER BY year ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail=f"Cash flow data for {ticker} not found")
        
    return [dict(row) for row in rows]


@router.get("/{ticker}/ratios")
def get_company_ratios(
    ticker: str, 
    year: Optional[str] = None
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Get pre-computed financial ratios for a company."""
    ticker = ticker.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if year is not None:
        year_str = str(year).strip()
        cursor.execute(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND (year = ? OR year LIKE ?) ORDER BY year ASC",
            (ticker, year_str, f"{year_str}%")
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            raise HTTPException(status_code=404, detail=f"Financial ratios for {ticker} in {year} not found")
        # Return single object if specific year requested, or array of matched
        return dict(rows[0])
    else:
        cursor.execute(
            "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year ASC",
            (ticker,)
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            raise HTTPException(status_code=404, detail=f"Financial ratios for {ticker} not found")
        return [dict(row) for row in rows]


@router.get("/{ticker}")
def get_company_profile(ticker: str) -> Dict[str, Any]:
    """Get full details for a single company."""
    ticker = ticker.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT c.*, s.broad_sector, s.sub_sector, s.index_weight_pct, s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON c.id = s.company_id
        WHERE c.id = ?
        """,
        (ticker,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Company {ticker} not found")
        
    return dict(row)