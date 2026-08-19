"""
db.py
-----
Shared SQLite connection helper + table registry for the FastAPI
layer (Day 38). Kept separate from src/dashboard/utils/db.py, which
is Streamlit-specific (uses @st.cache_data) - this module has no
Streamlit dependency so routers can import it cleanly.
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"

# The 10 core data-foundation tables tracked by the health endpoint.
# Excludes `analysis` (legacy/incomplete - only 4 companies, see
# src/screener/engine.py docstring), `prosandcons` (small NLP-derived
# side table), and `peer_percentiles` (a computed output table, not a
# primary data source) - those aren't part of the core 10-table data
# foundation this project loads from raw source data.
CORE_TABLES = [
    "companies",
    "sectors",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "financial_ratios",
    "market_cap",
    "stock_prices",
    "documents",
    "peer_groups",
]


def get_db_connection(db_path=DB_PATH):
    """
    Open a new SQLite connection. Rows come back as sqlite3.Row so
    routers can do dict(row) for easy JSON serialisation.

    Used as a FastAPI dependency:

        @router.get("/...")
        def endpoint(conn=Depends(get_db_connection)):
            ...
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_row_counts(db_path=DB_PATH, tables=None):
    """
    Row count for each table (dict of table_name -> count). Used by
    the /health endpoint. A table that fails to query (e.g. missing)
    reports None rather than raising, so one bad table doesn't take
    the whole health check down.
    """
    tables = tables or CORE_TABLES
    conn = sqlite3.connect(db_path)
    counts = {}
    try:
        for table in tables:
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
            except sqlite3.Error:
                counts[table] = None
    finally:
        conn.close()
    return counts
