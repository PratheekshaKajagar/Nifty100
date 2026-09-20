"""
tests/api/test_health.py
-------------------------
Day 42 - GET /api/v1/health returns HTTP 200 with status=ok and
db_row_counts containing all 10 core tables.
"""

from fastapi.testclient import TestClient

from src.api.db import CORE_TABLES
from src.api.main import app

client = TestClient(app)


def test_health_returns_200_and_status_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_health_db_row_counts_has_all_10_tables():
    resp = client.get("/api/v1/health")
    data = resp.json()
    counts = data["db_row_counts"]

    assert len(CORE_TABLES) == 10
    for table in CORE_TABLES:
        assert table in counts
        assert counts[table] is not None
        assert counts[table] > 0


def test_health_has_uptime_and_version():
    resp = client.get("/api/v1/health")
    data = resp.json()
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0
    assert "version" in data
    assert isinstance(data["version"], str)


def test_health_companies_table_has_92_rows():
    resp = client.get("/api/v1/health")
    data = resp.json()
    assert data["db_row_counts"]["companies"] == 92
