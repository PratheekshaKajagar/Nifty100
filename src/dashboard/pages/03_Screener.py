import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.dashboard.utils.db import get_companies, get_screener_data
from src.screener.engine import load_config

st.set_page_config(page_title="Screener | Nifty 100 Analytics", layout="wide")
st.title("🔍 Screener")

config = load_config()
companies = get_companies()
df = get_screener_data().merge(
    companies[["company_id", "company_name", "broad_sector"]],
    on="company_id",
    how="left",
    suffixes=("", "_c"),
)

# ---------------------------------------------------------
# Preset -> slider defaults mapping
# ---------------------------------------------------------
PRESET_LABELS = {
    "quality_compounder": "Quality",
    "value_pick": "Value",
    "growth_accelerator": "Growth",
    "dividend_champion": "Dividend",
    "debt_free_bluechip": "Debt-Free",
    "turnaround_watch": "Turnaround",
}

SLIDER_DEFAULTS = {
    "roe_min": 0,
    "de_max": 5.0,
    "fcf_min": -500,
    "revenue_cagr_min": -20,
    "pat_cagr_min": -20,
    "opm_min": 0,
    "pe_max": 100,
    "pb_max": 20,
    "div_yield_min": 0.0,
    "icr_min": 0.0,
}

RULE_TO_SLIDER = {
    "roe_min": "roe_min",
    "debt_to_equity_max": "de_max",
    "free_cash_flow_min": "fcf_min",
    "revenue_cagr_5yr_min": "revenue_cagr_min",
    "pat_cagr_5yr_min": "pat_cagr_min",
    "opm_min": "opm_min",
    "pe_max": "pe_max",
    "pb_max": "pb_max",
    "dividend_yield_min": "div_yield_min",
    "icr_min": "icr_min",
}

if "slider_values" not in st.session_state:
    st.session_state.slider_values = dict(SLIDER_DEFAULTS)

st.subheader("Presets")
preset_cols = st.columns(len(PRESET_LABELS))
for col, (preset_key, label) in zip(preset_cols, PRESET_LABELS.items()):
    if col.button(label, use_container_width=True):
        new_values = dict(SLIDER_DEFAULTS)
        for rule, threshold in config.get(preset_key, {}).items():
            slider_key = RULE_TO_SLIDER.get(rule)
            if slider_key:
                new_values[slider_key] = threshold
        st.session_state.slider_values = new_values

st.divider()

st.sidebar.header("Filters")
sv = st.session_state.slider_values

sv["roe_min"] = st.sidebar.slider("ROE min (%)", -20, 100, int(sv["roe_min"]))
sv["de_max"] = st.sidebar.slider("D/E max", 0.0, 15.0, float(sv["de_max"]), step=0.1)
sv["fcf_min"] = st.sidebar.slider("FCF min (Cr)", -2000, 5000, int(sv["fcf_min"]), step=50)
sv["revenue_cagr_min"] = st.sidebar.slider(
    "Revenue CAGR min (%)", -30, 60, int(sv["revenue_cagr_min"])
)
sv["pat_cagr_min"] = st.sidebar.slider("PAT CAGR min (%)", -30, 80, int(sv["pat_cagr_min"]))
sv["opm_min"] = st.sidebar.slider("OPM min (%)", -20, 60, int(sv["opm_min"]))
sv["pe_max"] = st.sidebar.slider("P/E max", 0, 150, int(sv["pe_max"]))
sv["pb_max"] = st.sidebar.slider("P/B max", 0.0, 30.0, float(sv["pb_max"]), step=0.5)
sv["div_yield_min"] = st.sidebar.slider(
    "Dividend Yield min (%)", 0.0, 10.0, float(sv["div_yield_min"]), step=0.1
)
sv["icr_min"] = st.sidebar.slider("ICR min", 0.0, 30.0, float(sv["icr_min"]), step=0.5)

# ---------------------------------------------------------
# Apply filters live
# ---------------------------------------------------------
filtered = df.copy()
filtered = filtered[filtered["return_on_equity_pct"] >= sv["roe_min"]]
filtered = filtered[
    (filtered["debt_to_equity"] <= sv["de_max"])
    | (filtered["broad_sector"].str.lower() == "financials")
]
filtered = filtered[filtered["free_cash_flow_cr"] >= sv["fcf_min"]]
filtered = filtered[filtered["compounded_sales_growth"] >= sv["revenue_cagr_min"]]
filtered = filtered[filtered["compounded_profit_growth"] >= sv["pat_cagr_min"]]
filtered = filtered[filtered["operating_profit_margin_pct"] >= sv["opm_min"]]
filtered = filtered[filtered["pe_ratio"] <= sv["pe_max"]]
filtered = filtered[filtered["pb_ratio"] <= sv["pb_max"]]
filtered = filtered[filtered["dividend_yield_pct"] >= sv["div_yield_min"]]
filtered = filtered[
    (filtered["interest_coverage"] >= sv["icr_min"]) | (filtered["interest_coverage"].isna())
]

filtered = filtered.sort_values("composite_quality_score", ascending=False)

st.markdown(f"**{len(filtered)} companies match your filters**")

display_cols = [
    "company_id",
    "company_name",
    "broad_sector",
    "composite_quality_score",
    "return_on_equity_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "compounded_sales_growth",
    "compounded_profit_growth",
    "operating_profit_margin_pct",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
    "interest_coverage",
]
display_df = filtered[display_cols].rename(
    columns={
        "company_id": "Ticker",
        "company_name": "Company",
        "broad_sector": "Sector",
        "composite_quality_score": "Composite Score",
        "return_on_equity_pct": "ROE %",
        "debt_to_equity": "D/E",
        "free_cash_flow_cr": "FCF (Cr)",
        "compounded_sales_growth": "Rev CAGR 5yr %",
        "compounded_profit_growth": "PAT CAGR 5yr %",
        "operating_profit_margin_pct": "OPM %",
        "pe_ratio": "P/E",
        "pb_ratio": "P/B",
        "dividend_yield_pct": "Div Yield %",
        "interest_coverage": "ICR",
    }
)

st.dataframe(display_df.round(2), use_container_width=True, hide_index=True)

csv_bytes = display_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download CSV",
    data=csv_bytes,
    file_name="screener_results.csv",
    mime="text/csv",
)
