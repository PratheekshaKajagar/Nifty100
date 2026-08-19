import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.dashboard.utils.db import get_companies, get_documents

st.set_page_config(page_title="Annual Reports | Nifty 100 Analytics", layout="wide")
st.title("📄 Annual Reports")

companies = get_companies()

options = [f"{row.company_id} — {row.company_name}" for row in companies.itertuples()]
query = st.text_input("Search company", "")
filtered_options = [o for o in options if query.lower() in o.lower()] if query else options

if not filtered_options:
    st.warning("Ticker not found — please try another")
    st.stop()

selection = st.selectbox("Company", filtered_options)
ticker = selection.split(" — ")[0]

docs = get_documents(ticker)

if docs.empty:
    st.info("No annual reports on file for this company.")
    st.stop()

st.markdown(f"**Available annual reports for {ticker}**")


@st.cache_data(ttl=3600, show_spinner=False)
def _check_url_available(url):
    """
    Best-effort HEAD request to see if the filing link is still live.
    Any network error, timeout, or non-2xx status is treated as
    unavailable rather than crashing the page.
    """
    try:
        import requests

        resp = requests.head(url, timeout=5, allow_redirects=True)
        if resp.status_code == 404:
            return False
        if resp.status_code >= 400:
            # Some BSE endpoints reject HEAD; fall back to a light GET
            resp = requests.get(url, timeout=5, stream=True)
            return resp.status_code < 400
        return True
    except Exception:
        return None  # unknown - couldn't verify (e.g. no network access)


for row in docs.itertuples():
    year = row.year
    url = row.annual_report

    col1, col2, col3 = st.columns([1, 4, 2])
    col1.write(f"**{int(year)}**" if year else "**N/A**")

    if isinstance(url, str) and url:
        col2.markdown(f"[Open report PDF]({url})")

        available = _check_url_available(url)
        if available is False:
            col3.markdown(":red[**Report unavailable**]")
        elif available is None:
            col3.caption("Availability not verified")
        else:
            col3.markdown(":green[Available]")
    else:
        col2.caption("No link on file")
        col3.markdown(":red[**Report unavailable**]")
