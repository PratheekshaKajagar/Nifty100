import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_companies, get_screener_data

st.set_page_config(page_title="Sector Analysis | Nifty 100 Analytics", layout="wide")
st.title("🏭 Sector Analysis")

companies = get_companies()
scored = get_screener_data().merge(
    companies[["company_id", "company_name", "broad_sector", "sub_sector"]],
    on="company_id",
    how="left",
    suffixes=("", "_c"),
)

sectors = sorted(scored["broad_sector"].dropna().unique().tolist())
selected_sector = st.selectbox("Sector", sectors)

sector_df = scored[scored["broad_sector"] == selected_sector].dropna(
    subset=["sales", "return_on_equity_pct", "market_cap_crore"]
)

st.subheader(f"{selected_sector} — Revenue vs ROE (bubble size = Market Cap)")

if sector_df.empty:
    st.info("No companies with complete data in this sector.")
else:
    fig = px.scatter(
        sector_df,
        x="sales",
        y="return_on_equity_pct",
        size="market_cap_crore",
        color="sub_sector",
        hover_name="company_name",
        labels={
            "sales": "Revenue (Cr)",
            "return_on_equity_pct": "ROE (%)",
            "market_cap_crore": "Market Cap (Cr)",
            "sub_sector": "Sub-Sector",
        },
        size_max=50,
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader(f"{selected_sector} — Median KPIs")

median_metrics = {
    "ROE (%)": scored[scored["broad_sector"] == selected_sector]["return_on_equity_pct"].median(),
    "D/E": scored[scored["broad_sector"] == selected_sector]["debt_to_equity"].median(),
    "OPM (%)": scored[scored["broad_sector"] == selected_sector][
        "operating_profit_margin_pct"
    ].median(),
    "P/E": scored[scored["broad_sector"] == selected_sector]["pe_ratio"].median(),
    "Composite Score": scored[scored["broad_sector"] == selected_sector][
        "composite_quality_score"
    ].median(),
}

import pandas as pd

median_df = pd.DataFrame(
    {"Metric": list(median_metrics.keys()), "Median Value": list(median_metrics.values())}
)

fig2 = px.bar(median_df, x="Metric", y="Median Value", text_auto=".1f")
fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10))
st.plotly_chart(fig2, use_container_width=True)
