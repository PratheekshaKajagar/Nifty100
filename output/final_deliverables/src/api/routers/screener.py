"""
screener.py
-----------
Thin wrapper around the existing src/screener/engine.py so the
quality-screener output is reachable over HTTP. Filter presets are
applied exactly as the CLI/dashboard already do; this router doesn't
reimplement any filtering logic.

Day 40 adds GET /api/v1/screener - the ad-hoc, slider-style screener
endpoint the spec calls for (min_roe, max_de, min_fcf, sector,
min_rev_cagr_5yr, min_pat_cagr_5yr, max_pe), independent of the
named presets.
"""

import math

from fastapi import APIRouter, HTTPException, Query

from src.api.db import DB_PATH
from src.screener.engine import (
    apply_filters,
    calculate_composite_score,
    load_config,
    load_screener_data,
)

router = APIRouter(prefix="/screener", tags=["screener"])

# Cache the loaded+scored universe for the lifetime of the process -
# it's read-only reference data (latest-year ratios), so there's no
# need to hit SQLite and recompute CAGR/composite scores on every
# request.
_SCREENER_CACHE = {"df": None}


def _get_scored_universe():
    if _SCREENER_CACHE["df"] is None:
        df = load_screener_data(str(DB_PATH))
        _SCREENER_CACHE["df"] = calculate_composite_score(df)
    return _SCREENER_CACHE["df"]


def _validate_positive(name: str, value):
    if value is not None and (not isinstance(value, (int, float)) or math.isnan(value)):
        raise HTTPException(status_code=400, detail=f"Invalid value for '{name}': {value!r}")


@router.get("/presets")
def list_presets():
    """List the named filter presets defined in config/screener_config.yaml."""
    config = load_config()
    return list(config.keys())


@router.get("/run")
def run_screener_preset(preset: str):
    """Run a named preset (Quality, Value, Growth, Dividend, Debt-Free, Turnaround)."""
    config = load_config()
    if preset not in config:
        raise HTTPException(status_code=404, detail=f"Unknown preset '{preset}'")

    df = load_screener_data(str(DB_PATH))
    result = apply_filters(df, preset)

    return {
        "preset": preset,
        "matched_count": len(result),
        "companies": result["company_id"].tolist(),
    }


@router.get("")
def run_screener(
    min_roe: float = Query(None, description="Minimum return_on_equity_pct"),
    max_de: float = Query(None, description="Maximum debt_to_equity"),
    min_fcf: float = Query(None, description="Minimum free_cash_flow_cr"),
    sector: str = Query(None, description="Filter to a single broad_sector"),
    min_rev_cagr_5yr: float = Query(None, description="Minimum 5yr revenue CAGR (%)"),
    min_pat_cagr_5yr: float = Query(None, description="Minimum 5yr PAT CAGR (%)"),
    max_pe: float = Query(None, description="Maximum P/E ratio"),
):
    """
    Day 40 - ad-hoc screener endpoint mirroring the dashboard's
    slider filters. Every parameter is optional; omitted ones are not
    filtered on. Returns HTTP 400 for a parameter that isn't a valid
    number (FastAPI's own float coercion already rejects most of
    these, but NaN - which parses fine as a float - is rejected here
    explicitly).
    """
    for name, value in (
        ("min_roe", min_roe),
        ("max_de", max_de),
        ("min_fcf", min_fcf),
        ("min_rev_cagr_5yr", min_rev_cagr_5yr),
        ("min_pat_cagr_5yr", min_pat_cagr_5yr),
        ("max_pe", max_pe),
    ):
        _validate_positive(name, value)

    df = _get_scored_universe()
    result = df.copy()

    if sector is not None:
        result = result[result["broad_sector"] == sector]
    if min_roe is not None:
        result = result[result["return_on_equity_pct"] >= min_roe]
    if max_de is not None:
        result = result[result["debt_to_equity"] <= max_de]
    if min_fcf is not None:
        result = result[result["free_cash_flow_cr"] >= min_fcf]
    if min_rev_cagr_5yr is not None:
        result = result[result["compounded_sales_growth"] >= min_rev_cagr_5yr]
    if min_pat_cagr_5yr is not None:
        result = result[result["compounded_profit_growth"] >= min_pat_cagr_5yr]
    if max_pe is not None:
        result = result[result["pe_ratio"] <= max_pe]

    result = result.sort_values("composite_quality_score", ascending=False)

    columns = [
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
    columns = [c for c in columns if c in result.columns]

    records = result[columns].replace({float("nan"): None}).to_dict(orient="records")

    return {
        "matched_count": len(records),
        "filters_applied": {
            "min_roe": min_roe,
            "max_de": max_de,
            "min_fcf": min_fcf,
            "sector": sector,
            "min_rev_cagr_5yr": min_rev_cagr_5yr,
            "min_pat_cagr_5yr": min_pat_cagr_5yr,
            "max_pe": max_pe,
        },
        "companies": records,
    }
