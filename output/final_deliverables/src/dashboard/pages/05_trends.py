import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import get_companies, get_ratios

st.set_page_config(page_title="Trend Analysis | Nifty 100 Analytics", layout="wide")
st.title("📈 Trend Analysis")

METRIC_OPTIONS = {
    "ROE (%)": "return_on_equity_pct",
    "Net Profit Margin (%)": "net_profit_margin_pct",
    "Operating Profit Margin (%)": "operating_profit_margin_pct",
    "Debt to Equity": "debt_to_equity",
    "Free Cash Flow (Cr)": "free_cash_flow_cr",
    "Interest Coverage": "interest_coverage",
    "Asset Turnover": "asset_turnover",
    "EPS": "earnings_per_share",
}

companies = get_companies()

options = [f"{row.company_id} — {row.company_name}" for row in companies.itertuples()]
query = st.text_input("Search company", "")
filtered_options = [o for o in options if query.lower() in o.lower()] if query else options

if not filtered_options:
    st.warning("Ticker not found — please try another")
    st.stop()

selection = st.selectbox("Company", filtered_options)
ticker = selection.split(" — ")[0]

selected_metrics = st.multiselect(
    "Metrics to overlay (up to 3)",
    list(METRIC_OPTIONS.keys()),
    default=["ROE (%)"],
    max_selections=3,
)

if not selected_metrics:
    st.info("Select at least one metric to plot.")
    st.stop()

history = get_ratios(ticker).dropna(subset=["year"]).sort_values("year").tail(10)

if history.empty:
    st.warning("No historical data available for this company.")
    st.stop()

fig = go.Figure()

for label in selected_metrics:
    col = METRIC_OPTIONS[label]
    series = history[["year", col]].dropna()
    if series.empty:
        continue

    fig.add_trace(
        go.Scatter(
            x=series["year"],
            y=series[col],
            mode="lines+markers",
            name=label,
        )
    )

    # YoY % change annotations
    yoy = series[col].pct_change() * 100
    for x, y, change in zip(series["year"], series[col], yoy):
        if pd.notna(change):
            fig.add_annotation(
                x=x,
                y=y,
                text=f"{change:+.1f}%",
                showarrow=False,
                yshift=12,
                font=dict(size=9),
            )

fig.update_layout(
    xaxis_title="Year",
    margin=dict(t=20, b=10, l=10, r=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)

st.plotly_chart(fig, use_container_width=True)

if len(history) < 10:
    st.caption(f"⚠️ Only {len(history)} years of data available for this company.")
