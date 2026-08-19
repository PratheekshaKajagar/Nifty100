import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_peer_groups_list,
    get_peers,
    get_screener_data,
)
from src.screener.engine import calculate_composite_score

st.set_page_config(page_title="Peer Comparison | Nifty 100 Analytics", layout="wide")
st.title("🤝 Peer Comparison")

RADAR_AXES = [
    ("roe_score", "ROE"),
    ("roce_score", "ROCE"),
    ("npm_score", "NPM"),
    ("de_score", "D/E"),
    ("fcf_cagr_score", "FCF Score"),
    ("pat_cagr_score", "PAT CAGR 5yr"),
    ("revenue_cagr_score", "Revenue CAGR 5yr"),
    ("composite_quality_score", "Composite Score"),
]

groups = get_peer_groups_list()

if not groups:
    st.warning("No peer groups found.")
    st.stop()

selected_group = st.selectbox("Peer Group", groups)

members = get_peers(selected_group)
companies = get_companies()

scored = get_screener_data()
scored = calculate_composite_score(scored)

group_data = members.merge(scored, on="company_id", how="left")

if group_data.empty:
    st.info("No companies found in this peer group.")
    st.stop()

company_options = [f"{row.company_id} — {row.company_name}" for row in group_data.itertuples()]
selected_company_label = st.selectbox("Company", company_options)
selected_ticker = selected_company_label.split(" — ")[0]

selected_row = group_data[group_data["company_id"] == selected_ticker].iloc[0]
peer_avg = group_data[[col for col, _ in RADAR_AXES]].mean()

# ---------------------------------------------------------
# Radar chart (Plotly Scatterpolar)
# ---------------------------------------------------------
categories = [label for _, label in RADAR_AXES]

company_values = [selected_row[col] for col, _ in RADAR_AXES]
peer_values = [peer_avg[col] for col, _ in RADAR_AXES]

fig = go.Figure()
fig.add_trace(
    go.Scatterpolar(
        r=company_values + [company_values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        name=selected_ticker,
    )
)
fig.add_trace(
    go.Scatterpolar(
        r=peer_values + [peer_values[0]],
        theta=categories + [categories[0]],
        name="Peer Group Average",
        line=dict(dash="dash"),
    )
)
fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
    showlegend=True,
    margin=dict(t=30, b=10, l=40, r=40),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------
# Side-by-side KPI table, benchmark row highlighted
# ---------------------------------------------------------
st.subheader(f"{selected_group} — All Members")

table_cols = [
    "company_id",
    "company_name",
    "is_benchmark",
    "return_on_equity_pct",
    "roce_percentage",
    "net_profit_margin_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "composite_quality_score",
]
table = (
    group_data[table_cols]
    .rename(
        columns={
            "company_id": "Ticker",
            "company_name": "Company",
            "is_benchmark": "Benchmark",
            "return_on_equity_pct": "ROE %",
            "roce_percentage": "ROCE %",
            "net_profit_margin_pct": "NPM %",
            "debt_to_equity": "D/E",
            "free_cash_flow_cr": "FCF (Cr)",
            "composite_quality_score": "Composite Score",
        }
    )
    .round(2)
)


def _highlight_benchmark(row):
    if row.get("Benchmark"):
        return ["background-color: #FFD966"] * len(row)
    return [""] * len(row)


st.dataframe(
    table.style.apply(_highlight_benchmark, axis=1),
    use_container_width=True,
    hide_index=True,
)
