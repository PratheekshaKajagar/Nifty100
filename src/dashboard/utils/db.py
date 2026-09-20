"""
db.py
-----
Shared, cached data-access layer for the Streamlit dashboard.
Every function that hits SQLite is wrapped with
@st.cache_data(ttl=600) so repeated navigation between screens
doesn't re-query the database every time.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"


def _connect():
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=600)
def get_companies():
    """All companies with sector + latest ROE/ROCE snapshot."""
    conn = _connect()
    df = pd.read_sql(
        """
        SELECT
            c.company_id,
            c.company_name,
            c.about_company,
            c.website,
            c.nse_profile,
            c.bse_profile,
            c.roce_percentage,
            c.roe_percentage,
            s.broad_sector,
            s.sub_sector
        FROM companies c
        LEFT JOIN sectors s ON c.company_id = s.company_id
        ORDER BY c.company_name
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_ratios(ticker, year=None):
    """Financial ratio history for a single company; filter to one year if given."""
    conn = _connect()
    query = "SELECT * FROM financial_ratios WHERE company_id = ?"
    params = [ticker]
    if year is not None:
        query += " AND year = ?"
        params.append(year)
    query += " ORDER BY year"
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_pl(ticker):
    """Profit & Loss history for a single company."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year",
        conn,
        params=[ticker],
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_bs(ticker):
    """Balance sheet history for a single company."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year",
        conn,
        params=[ticker],
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_cf(ticker):
    """Cash flow history for a single company."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT * FROM cashflow WHERE company_id = ? ORDER BY year",
        conn,
        params=[ticker],
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_sectors():
    """All sector assignments."""
    conn = _connect()
    df = pd.read_sql("SELECT * FROM sectors", conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_peers(group_name):
    """Members of a single peer group."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT * FROM peer_groups WHERE peer_group_name = ?",
        conn,
        params=[group_name],
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_valuation(ticker=None):
    """Valuation summary, optionally filtered to a single company."""
    conn = _connect()
    query = "SELECT * FROM market_cap"
    params = []
    if ticker is not None:
        query += " WHERE company_id = ?"
        params.append(ticker)
    query += " ORDER BY company_id, year"
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


GENERATED_PROS_CONS_PATH = PROJECT_ROOT / "output" / "pros_cons_generated.csv"


@st.cache_data(ttl=600)
def get_pros_cons(ticker):
    """
    Get pros/cons for a company.

    The raw `prosandcons` table (Screener.in source data) only covers a
    handful of companies - see Section 5.7 of the project spec ("Coverage
    gap: only ~8/92 companies"). Module 9's rule-based generator fills the
    rest (`src/nlp/pros_cons_generator.py`) and writes long-format rows
    (one per pro/con) to output/pros_cons_generated.csv, but that file was
    never wired into the dashboard's data layer, so every other company
    showed "No pros/cons data available".

    This prefers the manually curated raw-table entry when one exists for
    the ticker, and falls back to the auto-generated rows (reshaped into
    the same pros/cons wide-string shape the Company Profile page expects)
    for every other company.
    """
    conn = _connect()
    df = pd.read_sql(
        "SELECT pros, cons FROM prosandcons WHERE company_id = ?",
        conn,
        params=[ticker],
    )
    conn.close()

    if not df.empty and (df.iloc[0].get("pros") or df.iloc[0].get("cons")):
        return df

    if not GENERATED_PROS_CONS_PATH.exists():
        return df

    generated = pd.read_csv(GENERATED_PROS_CONS_PATH)
    company_rows = generated[generated["company_id"] == ticker]
    if company_rows.empty:
        return df

    pros_text = ". ".join(company_rows.loc[company_rows["type"] == "pro", "text"])
    cons_text = ". ".join(company_rows.loc[company_rows["type"] == "con", "text"])
    return pd.DataFrame([{"pros": pros_text or None, "cons": cons_text or None}])


@st.cache_data(ttl=600)
def get_documents(ticker):
    """Get documents."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT year, annual_report FROM documents WHERE company_id = ? ORDER BY year DESC",
        conn,
        params=[ticker],
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_peer_groups_list():
    """Get peer groups list."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT DISTINCT peer_group_name FROM peer_groups ORDER BY peer_group_name", conn
    )
    conn.close()
    return df["peer_group_name"].tolist()


@st.cache_data(ttl=600)
def get_screener_data():
    """Full latest-year screener dataset (composite score, CAGR, etc.)."""
    from src.screener.engine import (
        calculate_composite_score,
        calculate_sector_percentile,
        load_screener_data,
    )

    df = load_screener_data(str(DB_PATH))
    df = calculate_composite_score(df)
    df = calculate_sector_percentile(df)
    return df


@st.cache_data(ttl=600)
def get_capital_allocation():
    """Get capital allocation."""
    path = PROJECT_ROOT / "output" / "capital_allocation.csv"
    if not path.exists():
        return pd.DataFrame(columns=["company_id", "year", "pattern_label"])
    df = pd.read_csv(path)
    df = df.dropna(subset=["year"]).sort_values("year").groupby("company_id", as_index=False).last()
    return df


@st.cache_data(ttl=600)
def get_valuation_summary():
    """Get valuation summary."""
    from src.analytics.valuation import compute_valuation_table

    return compute_valuation_table(str(DB_PATH))