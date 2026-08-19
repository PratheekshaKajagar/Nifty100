"""
tests/api/test_companies.py
----------------------------
Day 39 - Tests for the /api/v1/companies endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

# Use a company we know exists from the DB inspection (ABB) and a
# clearly-invalid ticker for the 404 paths.
KNOWN_TICKER = "ABB"
UNKNOWN_TICKER = "NOTATICKER"


def test_list_companies():
    resp = client.get("/api/v1/companies")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    row = data[0]
    for key in ("company_id", "company_name", "broad_sector", "sub_sector", "roe_pct", "roce_pct"):
        assert key in row


def test_list_companies_search_filter():
    resp = client.get("/api/v1/companies", params={"search": "ABB"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(row["company_id"] == KNOWN_TICKER for row in data)


def test_list_companies_sector_filter():
    resp = client.get("/api/v1/companies")
    sectors = {row["broad_sector"] for row in resp.json() if row["broad_sector"]}
    a_sector = next(iter(sectors))

    resp = client.get("/api/v1/companies", params={"sector": a_sector})
    assert resp.status_code == 200
    data = resp.json()
    assert all(row["broad_sector"] == a_sector for row in data)


def test_get_company_profile():
    resp = client.get(f"/api/v1/companies/{KNOWN_TICKER}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == KNOWN_TICKER
    assert "broad_sector" in data
    assert "latest_kpis" in data


def test_get_company_profile_404():
    resp = client.get(f"/api/v1/companies/{UNKNOWN_TICKER}")
    assert resp.status_code == 404


def test_company_pl_history():
    resp = client.get(f"/api/v1/companies/{KNOWN_TICKER}/pl")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert all(row["company_id"] == KNOWN_TICKER for row in data)


def test_company_pl_year_filter():
    resp = client.get(
        f"/api/v1/companies/{KNOWN_TICKER}/pl",
        params={"from_year": "2020-01", "to_year": "2022-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(2020 <= row["year"] <= 2022 for row in data)


def test_company_pl_404_unknown_ticker():
    resp = client.get(f"/api/v1/companies/{UNKNOWN_TICKER}/pl")
    assert resp.status_code == 404


def test_company_balance_sheet():
    resp = client.get(f"/api/v1/companies/{KNOWN_TICKER}/bs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_company_cashflow():
    resp = client.get(f"/api/v1/companies/{KNOWN_TICKER}/cashflow")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_company_ratios_all_years():
    resp = client.get(f"/api/v1/companies/{KNOWN_TICKER}/ratios")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_company_ratios_single_year():
    all_years = client.get(f"/api/v1/companies/{KNOWN_TICKER}/ratios").json()
    if not all_years:
        pytest.skip("No ratio rows for this ticker to test single-year filter against")
    a_year = int(all_years[0]["year"])

    resp = client.get(f"/api/v1/companies/{KNOWN_TICKER}/ratios", params={"year": str(a_year)})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert int(data["year"]) == a_year


def test_company_tearsheet_download():
    resp = client.get(f"/api/v1/companies/{KNOWN_TICKER}/tearsheet")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_company_tearsheet_404_unknown_ticker():
    resp = client.get(f"/api/v1/companies/{UNKNOWN_TICKER}/tearsheet")
    assert resp.status_code == 404
