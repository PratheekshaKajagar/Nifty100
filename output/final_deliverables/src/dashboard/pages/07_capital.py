import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_capital_allocation, get_companies

st.set_page_config(page_title="Capital Allocation Map | Nifty 100 Analytics", layout="wide")
st.title("🗺️ Capital Allocation Map")

st.caption(
    "Each company is classified by its most recent cash-flow sign pattern "
    "(CFO / CFI / CFF) into one of 8 capital allocation archetypes."
)

alloc = get_capital_allocation()
companies = get_companies()

if alloc.empty:
    st.warning("No capital allocation data available.")
    st.stop()

merged = alloc.merge(
    companies[["company_id", "company_name", "broad_sector"]],
    on="company_id",
    how="left",
)

pattern_counts = merged.groupby("pattern_label")["company_id"].count().reset_index()
pattern_counts.columns = ["pattern_label", "count"]

fig = px.treemap(
    merged,
    path=["pattern_label", "company_id"],
    values=None,
    color="pattern_label",
)
fig.update_traces(root_color="lightgrey")
fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))

st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Browse by Pattern")
selected_pattern = st.selectbox(
    "Capital Allocation Pattern", sorted(merged["pattern_label"].unique())
)

pattern_companies = merged[merged["pattern_label"] == selected_pattern][
    ["company_id", "company_name", "broad_sector"]
].rename(columns={"company_id": "Ticker", "company_name": "Company", "broad_sector": "Sector"})

st.markdown(f"**{len(pattern_companies)} companies classified as _{selected_pattern}_**")
st.dataframe(pattern_companies, use_container_width=True, hide_index=True)
