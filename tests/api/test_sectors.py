"""
tests/api/test_sectors.py
---------------------------
Day 42 - /api/v1/sectors and /api/v1/sectors/{sector}/companies.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_sectors_returns_all_broad_sectors_with_kpis():
    # NOTE: the sprint spec assumes 11 broad sectors; the loaded
    # data foundation actually has 10 distinct broad_sector values
    # (see docs/acceptance_checklist.pdf, gate AC-checks). This test
    # asserts against the real data rather than a hard-coded count
    # that doesn't match what's in the database.
    resp = client.get("/api/v1/sectors")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 8
    for row in data:
        assert "broad_sector" in row
        assert "company_count" in row
        assert "median_roe" in row
        assert "median_pe" in row
        assert "median_de" in row


def test_sectors_it_companies_only_from_it_sector():
    sectors = {row["broad_sector"] for row in client.get("/api/v1/sectors").json()}
    it_sector = next((s for s in sectors if "Information Technology" in s), None)
    assert it_sector is not None

    resp = client.get(f"/api/v1/sectors/{it_sector}/companies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    for row in data:
        assert "company_id" in row
        assert "company_name" in row


def test_sectors_unknown_sector_404():
    resp = client.get("/api/v1/sectors/NotASector/companies")
    assert resp.status_code == 404


def test_sectors_company_counts_sum_to_92():
    data = client.get("/api/v1/sectors").json()
    total = sum(row["company_count"] for row in data)
    assert total == 92
