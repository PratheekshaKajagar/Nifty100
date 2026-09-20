import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import DB_PATH, get_companies

st.set_page_config(page_title="Home | Nifty 100 Analytics", layout="wide")
st.title("🏠 Home")

# ---------------------------------------------------------
# Year selector (sidebar) - all metrics on this page update
# ---------------------------------------------------------
YEARS = list(range(2019, 2025))
selected_year = st.sidebar.selectbox("Year", YEARS, index=len(YEARS) - 1)


@st.cache_data(ttl=600)
def load_year_snapshot(year):
    """Load year snapshot."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """
        SELECT
            fr.company_id, fr.year,
            fr.return_on_equity_pct, fr.debt_to_equity,
            mc.pe_ratio,
            s.broad_sector
        FROM financial_ratios fr
        LEFT JOIN market_cap mc
            ON fr.company_id = mc.company_id AND fr.year = mc.year
        LEFT JOIN sectors s ON fr.company_id = s.company_id
        WHERE fr.year = ?
        """,
        conn,
        params=[year],
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_revenue_cagr():
    # Reuses the screener's already-validated 5yr CAGR calculation
    """Load revenue cagr."""
    from src.dashboard.utils.db import get_screener_data

    return get_screener_data()[["company_id", "compounded_sales_growth", "debt_to_equity"]]


snapshot = load_year_snapshot(selected_year)
cagr = load_revenue_cagr()
companies = get_companies()

# ---------------------------------------------------------
# 6 KPI Tiles
# ---------------------------------------------------------
avg_roe = snapshot["return_on_equity_pct"].mean()
median_pe = snapshot["pe_ratio"].median()
median_de = snapshot["debt_to_equity"].median()
total_companies = companies["company_id"].nunique()
median_rev_cagr = cagr["compounded_sales_growth"].median()
debt_free_count = (
    int((cagr["debt_to_equity"] == 0).sum())
    if "debt_to_equity" in cagr
    else int((snapshot["debt_to_equity"] == 0).sum())
)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Average ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A")
c2.metric("Median P/E", f"{median_pe:.1f}" if pd.notna(median_pe) else "N/A")
c3.metric("Median D/E", f"{median_de:.2f}" if pd.notna(median_de) else "N/A")
c4.metric("Total Companies", total_companies)
c5.metric(
    "Median Revenue CAGR 5yr", f"{median_rev_cagr:.1f}%" if pd.notna(median_rev_cagr) else "N/A"
)
c6.metric("Debt-Free Companies", debt_free_count)

st.divider()

col_left, col_right = st.columns([1, 1])

# ---------------------------------------------------------
# Sector breakdown donut chart
# ---------------------------------------------------------
with col_left:
    st.subheader("Sector Breakdown")
    sector_counts = companies["broad_sector"].value_counts().reset_index()
    sector_counts.columns = ["broad_sector", "count"]
    fig = px.pie(
        sector_counts,
        names="broad_sector",
        values="count",
        hole=0.5,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# Top-5 companies by composite quality score
# ---------------------------------------------------------
with col_right:
    st.subheader("Top 5 by Composite Quality Score")
    from src.dashboard.utils.db import get_screener_data

    scored = get_screener_data()
    top5 = scored.sort_values("composite_quality_score", ascending=False).head(5)
    top5 = top5.merge(
        companies[["company_id", "company_name"]], on="company_id", how="left", suffixes=("", "_c")
    )
    display_cols = ["company_id", "company_name", "broad_sector", "composite_quality_score"]
    st.dataframe(
        top5[display_cols]
        .rename(
            columns={
                "company_id": "Ticker",
                "company_name": "Company",
                "broad_sector": "Sector",
                "composite_quality_score": "Composite Score",
            }
        )
        .round(1),
        use_container_width=True,
        hide_index=True,
    )
