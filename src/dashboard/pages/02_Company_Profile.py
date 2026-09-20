import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_pl,
    get_pros_cons,
    get_ratios,
)

st.set_page_config(page_title="Company Profile | Nifty 100 Analytics", layout="wide")
st.title("🏢 Company Profile")

companies = get_companies()

# ---------------------------------------------------------
# Search box with autocomplete-style dropdown
# ---------------------------------------------------------
options = [f"{row.company_id} — {row.company_name}" for row in companies.itertuples()]
query = st.text_input("Search by company name or ticker", "")

filtered_options = [o for o in options if query.lower() in o.lower()] if query else options

if not filtered_options:
    st.warning("Ticker not found — please try another")
    st.stop()

selection = st.selectbox("Select company", filtered_options)
ticker = selection.split(" — ")[0]

company_row = companies[companies["company_id"] == ticker]

if company_row.empty:
    st.warning("Ticker not found — please try another")
    st.stop()

company = company_row.iloc[0]

# ---------------------------------------------------------
# Company card
# ---------------------------------------------------------
st.subheader(f"{company['company_name']} ({ticker})")
st.caption(
    f"{company.get('broad_sector', 'N/A')} · {company.get('sub_sector', 'N/A')} · NSE: {ticker}"
)
about = company.get("about_company")
st.write(about if isinstance(about, str) and about else "No description available.")

st.divider()

# ---------------------------------------------------------
# 6 KPI Tiles (latest year)
# ---------------------------------------------------------
ratios = get_ratios(ticker)

if ratios.empty:
    st.warning("No financial data available for this company.")
    st.stop()

latest = ratios.sort_values("year").iloc[-1]


def _fmt(value, suffix=""):
    return f"{value:.1f}{suffix}" if pd.notna(value) else "N/A"


k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("ROE", _fmt(latest.get("return_on_equity_pct"), "%"))
k2.metric("ROCE", _fmt(company.get("roce_percentage"), "%"))
k3.metric("Net Profit Margin", _fmt(latest.get("net_profit_margin_pct"), "%"))
k4.metric("D/E", _fmt(latest.get("debt_to_equity")))
k5.metric("FCF (latest year)", _fmt(latest.get("free_cash_flow_cr"), " Cr"))

from src.screener.engine import load_screener_data

_screener_row = load_screener_data(
    str(Path(__file__).resolve().parents[3] / "data" / "nifty100.db")
)
_screener_row = _screener_row[_screener_row["company_id"] == ticker]
rev_cagr = _screener_row["compounded_sales_growth"].iloc[0] if not _screener_row.empty else None
k6.metric("Revenue CAGR 5yr", _fmt(rev_cagr, "%"))

st.divider()

# ---------------------------------------------------------
# 10-year Revenue & Net Profit bar chart
# ---------------------------------------------------------
pl = get_pl(ticker).dropna(subset=["year"]).sort_values("year").tail(10)

if not pl.empty:
    st.subheader("Revenue & Net Profit (10yr)")
    if len(pl) < 10:
        st.caption(f"⚠️ Only {len(pl)} years of data available for this company.")
    fig = go.Figure()
    fig.add_bar(x=pl["year"], y=pl["sales"], name="Revenue")
    fig.add_bar(x=pl["year"], y=pl["net_profit"], name="Net Profit")
    fig.update_layout(barmode="group", margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No 10-year P&L history available for this company.")

# ---------------------------------------------------------
# ROE / ROCE dual-axis line chart
# ---------------------------------------------------------
st.subheader("ROE Trend (10yr)")
roe_hist = ratios.dropna(subset=["year"]).sort_values("year").tail(10)

if not roe_hist.empty:
    st.caption(
        "Note: ROCE is only available as a single current-year figure in the source data "
        "(not a historical series), so it's shown as a flat reference line."
    )
    if len(roe_hist) < 10:
        st.caption(f"⚠️ Only {len(roe_hist)} years of data available for this company.")
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=roe_hist["year"],
            y=roe_hist["return_on_equity_pct"],
            name="ROE (%)",
            mode="lines+markers",
            yaxis="y1",
        )
    )
    roce_current = company.get("roce_percentage")
    if pd.notna(roce_current):
        fig2.add_trace(
            go.Scatter(
                x=roe_hist["year"],
                y=[roce_current] * len(roe_hist),
                name="ROCE (current, %)",
                mode="lines",
                line=dict(dash="dash"),
                yaxis="y2",
            )
        )
    fig2.update_layout(
        yaxis=dict(title="ROE (%)"),
        yaxis2=dict(title="ROCE (%)", overlaying="y", side="right"),
        margin=dict(t=10, b=10, l=10, r=10),
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No ROE history available for this company.")

st.divider()

# ---------------------------------------------------------
# Pros & Cons badges
# ---------------------------------------------------------
st.subheader("Pros & Cons")
pc = get_pros_cons(ticker)

pcol1, pcol2 = st.columns(2)

if not pc.empty:
    pros_text = pc.iloc[0].get("pros")
    cons_text = pc.iloc[0].get("cons")

    with pcol1:
        st.markdown("**✅ Pros**")
        if isinstance(pros_text, str) and pros_text:
            for line in [p.strip() for p in pros_text.split(".") if p.strip()]:
                st.success(f"✔ {line}")
        else:
            st.caption("No pros listed.")

    with pcol2:
        st.markdown("**❌ Cons**")
        if isinstance(cons_text, str) and cons_text:
            for line in [c.strip() for c in cons_text.split(".") if c.strip()]:
                st.error(f"✘ {line}")
        else:
            st.caption("No cons listed.")
else:
    st.caption("No pros/cons data available for this company.")
