"""
portfolio.py
------------
Portfolio-wide analytics: KMeans cluster assignments/profiles (Day 36
& 37) and the aggregate KPI statistics / outlier report (Day 37).
Reads the pre-generated CSVs under output/ rather than recomputing on
every request - the clustering/stats pipeline is a batch job, not
something that should run per HTTP call.
"""

import pandas as pd
from fastapi import APIRouter, HTTPException

from src.api.db import PROJECT_ROOT

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

OUTPUT_DIR = PROJECT_ROOT / "output"


def _read_csv_or_404(filename):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"'{filename}' has not been generated yet - "
                "run the corresponding analytics job first."
            ),
        )
    return pd.read_csv(path)


@router.get("/clusters")
def cluster_assignments():
    """Cluster assignments."""
    df = _read_csv_or_404("cluster_labels.csv")
    return df.to_dict(orient="records")


@router.get("/clusters/profile")
def cluster_profile():
    """Cluster profile."""
    df = _read_csv_or_404("cluster_profile.csv")
    return df.to_dict(orient="records")


@router.get("/stats")
def portfolio_stats():
    """Portfolio stats."""
    df = _read_csv_or_404("portfolio_stats.csv")
    return df.to_dict(orient="records")


@router.get("/outliers")
def outlier_report():
    """Outlier report."""
    df = _read_csv_or_404("outlier_report.csv")
    return df.to_dict(orient="records")
