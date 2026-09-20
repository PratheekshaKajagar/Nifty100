"""
tests/api/test_screener.py
----------------------------
Day 42 - GET /api/v1/screener (ad-hoc filter endpoint).
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_screener_min_roe_filters_correctly():
    resp = client.get("/api/v1/screener", params={"min_roe": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_count"] == len(data["companies"])
    for row in data["companies"]:
        if row["return_on_equity_pct"] is not None:
            assert row["return_on_equity_pct"] >= 15


def test_screener_no_filters_returns_full_universe():
    resp = client.get("/api/v1/screener")
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_count"] > 0


def test_screener_sector_filter():
    resp = client.get("/api/v1/screener", params={"sector": "Information Technology"})
    assert resp.status_code == 200
    data = resp.json()
    for row in data["companies"]:
        assert row["broad_sector"] == "Information Technology"


def test_screener_invalid_parameter_returns_400():
    # FastAPI/pydantic rejects a non-numeric value for a float query
    # param with its own validation (422); a NaN literal passes
    # float parsing but is explicitly rejected by the router (400).
    resp = client.get("/api/v1/screener", params={"min_roe": "nan"})
    assert resp.status_code == 400


def test_screener_combined_filters():
    resp = client.get(
        "/api/v1/screener",
        params={"min_roe": 10, "max_de": 2, "max_pe": 60},
    )
    assert resp.status_code == 200
    data = resp.json()
    for row in data["companies"]:
        if row["return_on_equity_pct"] is not None:
            assert row["return_on_equity_pct"] >= 10
        if row["debt_to_equity"] is not None:
            assert row["debt_to_equity"] <= 2
        if row["pe_ratio"] is not None:
            assert row["pe_ratio"] <= 60


def test_screener_presets_list():
    resp = client.get("/api/v1/screener/presets")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) > 0


def test_screener_run_preset():
    presets = client.get("/api/v1/screener/presets").json()
    resp = client.get("/api/v1/screener/run", params={"preset": presets[0]})
    assert resp.status_code == 200
    assert "matched_count" in resp.json()


def test_screener_run_unknown_preset_404():
    resp = client.get("/api/v1/screener/run", params={"preset": "NotARealPreset"})
    assert resp.status_code == 404
