"""
health.py
---------
GET /api/v1/health

Returns overall API status, a row count per core table (so a broken
ETL run / empty DB is visible immediately), process uptime, and the
API version string.
"""

import time

from fastapi import APIRouter

from src.api.db import get_row_counts

router = APIRouter(prefix="/health", tags=["health"])

API_VERSION = "0.1.0"
_START_TIME = time.time()


@router.get("")
def health_check():
    """Health check."""
    return {
        "status": "ok",
        "db_row_counts": get_row_counts(),
        "uptime_seconds": round(time.time() - _START_TIME, 2),
        "version": API_VERSION,
    }
