"""
companies.py
------------
Day 39 - Company data endpoints.

Company master data + full financial history (P&L, balance sheet,
cash flow, ratios) + tearsheet PDF download, all keyed on the
company's ticker (== `company_id` in the DB, e.g. "TCS", "ABB").
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from src.api.db import DB_PATH, PROJECT_ROOT, get_db_connection

router = APIRouter(prefix="/companies", tags=["companies"])

TEARSHEET_DIR = PROJECT_ROOT / "reports" / "tearsheets"

# Cache the scored universe (used by the /peers/compare radar
# endpoint) for the lifetime of the process - it's read-only
# reference data.
_RADAR_CACHE = {"df": None}


def _clean(value):
    """NaN -> None so FastAPI's JSON encoder doesn't choke on it."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _year_from_param(value: str | None) -> int | None:
    """
    from_year / to_year come in as "YYYY" or "YYYY-MM" per the spec.
    The DB only stores a plain integer year, so this just pulls the
    year portion out and ignores any month suffix.
    """
    if value is None:
        return None
    year_part = str(value).split("-")[0]
    try:
        return int(year_part)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid year value '{value}' - expected YYYY or YYYY-MM",
        )


def _require_company(company_id: str, conn):
    """404s early if the ticker doesn't exist, so downstream endpoints
    don't need to special-case 'exists but no rows for that table'."""
    row = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (company_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")


def _year_filtered_history(conn, table: str, company_id: str, from_year, to_year, order="ASC"):
    query = f"SELECT * FROM {table} WHERE company_id = ?"
    params = [company_id]

    if from_year is not None:
        query += " AND year >= ?"
        params.append(from_year)
    if to_year is not None:
        query += " AND year <= ?"
        params.append(to_year)

    query += f" ORDER BY year {order}"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


# ----------------------------------------------------
# GET /companies
# ----------------------------------------------------
@router.get("")
def list_companies(
    sector: str | None = Query(None, description="Filter by broad_sector"),
    market_cap_category: str | None = Query(None, description="Filter by market_cap_category"),
    search: str | None = Query(None, description="Partial match on company name or ticker"),
    conn=Depends(get_db_connection),
):
    """List companies."""
    query = """
        SELECT
            c.company_id, c.company_name, s.broad_sector, s.sub_sector,
            c.roe_percentage AS roe_pct, c.roce_percentage AS roce_pct
        FROM companies c
        LEFT JOIN sectors s ON c.company_id = s.company_id
        WHERE 1=1
    """
    params = []

    if sector:
        query += " AND s.broad_sector = ?"
        params.append(sector)

    if market_cap_category:
        query += " AND s.market_cap_category = ?"
        params.append(market_cap_category)

    if search:
        query += " AND (c.company_name LIKE ? OR c.company_id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])

    query += " ORDER BY c.company_name"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


# ----------------------------------------------------
# GET /companies/{ticker}
# ----------------------------------------------------
@router.get("/{ticker}")
def get_company(ticker: str, conn=Depends(get_db_connection)):
    """Get company."""
    row = conn.execute(
        """
        SELECT
            c.*, s.broad_sector, s.sub_sector, s.index_weight_pct, s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON c.company_id = s.company_id
        WHERE c.company_id = ?
        """,
        (ticker,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    profile = dict(row)

    latest_kpis = conn.execute(
        """
        SELECT * FROM financial_ratios
        WHERE company_id = ?
        ORDER BY year DESC
        LIMIT 1
        """,
        (ticker,),
    ).fetchone()

    profile["latest_kpis"] = dict(latest_kpis) if latest_kpis else None

    return profile


# ----------------------------------------------------
# GET /companies/{ticker}/pl
# ----------------------------------------------------
@router.get("/{ticker}/pl")
def company_pl(
    ticker: str,
    from_year: str | None = Query(None, description="YYYY or YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY or YYYY-MM"),
    conn=Depends(get_db_connection),
):
    """Company pl."""
    _require_company(ticker, conn)
    return _year_filtered_history(
        conn,
        "profitandloss",
        ticker,
        _year_from_param(from_year),
        _year_from_param(to_year),
    )


# ----------------------------------------------------
# GET /companies/{ticker}/bs
# ----------------------------------------------------
@router.get("/{ticker}/bs")
def company_balance_sheet(
    ticker: str,
    from_year: str | None = Query(None, description="YYYY or YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY or YYYY-MM"),
    conn=Depends(get_db_connection),
):
    """Company balance sheet."""
    _require_company(ticker, conn)
    return _year_filtered_history(
        conn,
        "balancesheet",
        ticker,
        _year_from_param(from_year),
        _year_from_param(to_year),
    )


# ----------------------------------------------------
# GET /companies/{ticker}/cashflow
# ----------------------------------------------------
@router.get("/{ticker}/cashflow")
def company_cashflow(
    ticker: str,
    from_year: str | None = Query(None, description="YYYY or YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY or YYYY-MM"),
    conn=Depends(get_db_connection),
):
    """Company cashflow."""
    _require_company(ticker, conn)
    return _year_filtered_history(
        conn,
        "cashflow",
        ticker,
        _year_from_param(from_year),
        _year_from_param(to_year),
    )


# ----------------------------------------------------
# GET /companies/{ticker}/ratios
# ----------------------------------------------------
@router.get("/{ticker}/ratios")
def company_ratios(
    ticker: str,
    year: str | None = Query(None, description="Return a single year's ratios (YYYY or YYYY-MM)"),
    conn=Depends(get_db_connection),
):
    """Company ratios."""
    _require_company(ticker, conn)

    if year is not None:
        year_int = _year_from_param(year)
        row = conn.execute(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?",
            (ticker, year_int),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No ratios for '{ticker}' in year {year_int}",
            )
        return dict(row)

    rows = conn.execute(
        "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
        (ticker,),
    ).fetchall()
    return [dict(row) for row in rows]


# ----------------------------------------------------
# GET /companies/{ticker}/tearsheet
# ----------------------------------------------------
@router.get("/{ticker}/tearsheet")
def company_tearsheet(ticker: str, conn=Depends(get_db_connection)):
    """Company tearsheet."""
    _require_company(ticker, conn)

    pdf_path = TEARSHEET_DIR / f"{ticker}_tearsheet.pdf"
    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Tearsheet not yet generated for '{ticker}'",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{ticker}_tearsheet.pdf",
    )


# ----------------------------------------------------
# GET /companies/{ticker}/peers/compare
# Day 40 - radar data: the company's 8 axis metrics, its peer
# group's average for the same 8 metrics, and the peer group's
# designated benchmark company.
# ----------------------------------------------------
@router.get("/{ticker}/peers/compare")
def company_peer_radar(ticker: str, conn=Depends(get_db_connection)):
    """Company peer radar."""
    _require_company(ticker, conn)

    from src.analytics.radar import RADAR_AXES, _prepare_scored_data

    if _RADAR_CACHE["df"] is None:
        _RADAR_CACHE["df"] = _prepare_scored_data(str(DB_PATH))
    df = _RADAR_CACHE["df"]

    company_rows = df[df["company_id"] == ticker]
    if company_rows.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No screener/ratio data available for '{ticker}' to build a radar",
        )
    company_row = company_rows.iloc[0]

    peer_group_name = company_row.get("peer_group_name")
    axis_cols = [col for col, _ in RADAR_AXES]

    company_metrics = {label: _clean(company_row.get(col)) for col, label in RADAR_AXES}

    result = {
        "company_id": ticker,
        "peer_group_name": peer_group_name if isinstance(peer_group_name, str) else None,
        "axes": [label for _, label in RADAR_AXES],
        "company": company_metrics,
        "peer_group_average": None,
        "benchmark": None,
    }

    if isinstance(peer_group_name, str):
        peers = df[df["peer_group_name"] == peer_group_name]
        peer_avg = peers[axis_cols].mean(numeric_only=True)
        result["peer_group_average"] = {
            label: _clean(peer_avg.get(col)) for col, label in RADAR_AXES
        }

        benchmark_row = (
            peers[peers["is_benchmark"].astype(bool)]
            if "is_benchmark" in peers.columns
            else peers.iloc[0:0]
        )
        if not benchmark_row.empty:
            b = benchmark_row.iloc[0]
            result["benchmark"] = {
                "company_id": b["company_id"],
                "metrics": {label: _clean(b.get(col)) for col, label in RADAR_AXES},
            }

    return result


# ----------------------------------------------------
# GET /companies/{ticker}/documents
# Day 40 - annual report links with an is_url_valid flag per year.
# ----------------------------------------------------
@router.get("/{ticker}/documents")
def company_documents(ticker: str, conn=Depends(get_db_connection)):
    """Company documents."""
    _require_company(ticker, conn)

    rows = conn.execute(
        "SELECT year, annual_report FROM documents WHERE company_id = ? ORDER BY year DESC",
        (ticker,),
    ).fetchall()

    documents = []
    for row in rows:
        link = row["annual_report"]
        documents.append(
            {
                "year": row["year"],
                "annual_report": link,
                "is_url_valid": bool(link)
                and isinstance(link, str)
                and link.strip().lower().startswith("http"),
            }
        )

    return {"company_id": ticker, "documents": documents}
