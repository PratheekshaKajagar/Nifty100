"""
main.py
-------
Day 38 - FastAPI application scaffold.

Run locally with:
    uvicorn src.api.main:app --reload

All routers are mounted under /api/v1. See src/api/routers/ for one
file per module (companies, screener, sectors, peers, valuation,
portfolio, documents, health).
"""

import logging
import sqlite3
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.db import DB_PATH
from src.api.routers import (
    companies,
    documents,
    health,
    market_cap,
    peers,
    portfolio,
    screener,
    sectors,
    valuation,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nifty100.api")

app = FastAPI(
    title="Nifty100 Data Foundation API",
    description="Internal API over the Nifty100 fundamentals/screener/analytics data foundation.",
    version=health.API_VERSION,
)

# ----------------------------------------------------
# CORS - internal use only, so all origins are allowed.
# ----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------
# Request logging middleware - method, path, response time,
# for every request.
# ----------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log requests."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "%s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    return response


# ----------------------------------------------------
# SQLite connection function
# ----------------------------------------------------
def get_connection():
    """
    Open a single-use SQLite connection to the project database.
    Routers should generally prefer the `get_db_connection`
    dependency in src/api/db.py (which handles closing automatically
    via FastAPI's Depends), but this is kept here as the simple,
    direct connection function the spec calls for.
    """
    return sqlite3.connect(DB_PATH)


# ----------------------------------------------------
# Routers, all under /api/v1
# ----------------------------------------------------
# Note: Since each sub-router (e.g. companies.py) defines its own 
# prefix like '/api/v1/companies', mounting with prefix="" ensures 
# paths resolve cleanly without doubling to '/api/v1/api/v1/...'.
app.include_router(health.router)
app.include_router(companies.router)
app.include_router(screener.router)
app.include_router(sectors.router)
app.include_router(peers.router)
app.include_router(valuation.router)
app.include_router(market_cap.router)
app.include_router(portfolio.router)
app.include_router(documents.router)


@app.get("/")
def root():
    """Root."""
    return {
        "name": "Nifty100 Data Foundation API",
        "version": health.API_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }