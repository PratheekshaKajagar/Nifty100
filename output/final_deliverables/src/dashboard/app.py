"""
app.py
------
Main Streamlit entry point for the Nifty 100 Analytics dashboard.

Run with:
    streamlit run src/dashboard/app.py

Streamlit auto-discovers the sibling `pages/` directory and builds
the sidebar navigation for all 8 screens automatically.
"""

import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Nifty 100 Analytics")

st.markdown("""
    Welcome to the Nifty 100 Analytics dashboard.

    Use the sidebar to navigate between screens:

    - **🏠 Home** — universe-level KPIs and sector breakdown
    - **🏢 Company Profile** — deep dive on a single company
    - **🔍 Screener** — filter the universe with sliders or presets
    - **🤝 Peer Comparison** — a company vs. its peer group
    - **📈 Trend Analysis** — multi-metric 10-year trends
    - **🏭 Sector Analysis** — bubble chart + sector medians
    - **🗺️ Capital Allocation Map** — treemap of capital allocation patterns
    - **📄 Annual Reports** — links to filed annual reports

    Data covers all 92 companies in the Nifty 100 universe.
    """)

st.info("Pick a screen from the sidebar to get started.")
