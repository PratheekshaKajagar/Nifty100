import numpy as np
import pandas as pd
import pytest

from src.analytics.clustering import (
    FEATURES,
    N_CLUSTERS,
    impute_sector_median,
    run_clustering,
    scale_features,
)

DB_PATH = "data/nifty100.db"


@pytest.fixture
def toy_df():
    return pd.DataFrame(
        {
            "company_id": ["A", "B", "C", "D"],
            "broad_sector": ["Tech", "Tech", "Energy", "Energy"],
            "return_on_equity_pct": [10.0, np.nan, 20.0, 30.0],
            "debt_to_equity": [0.5, 1.5, np.nan, np.nan],
            "revenue_cagr_5yr": [5.0, 7.0, 9.0, np.nan],
            "fcf_cagr_5yr": [1.0, 3.0, np.nan, np.nan],
            "operating_profit_margin_pct": [10.0, 20.0, 30.0, 40.0],
        }
    )


def test_impute_sector_median_fills_within_sector(toy_df):
    out = impute_sector_median(toy_df)

    assert out["return_on_equity_pct"].isna().sum() == 0
    # Tech sector median ROE is 10 (only A has a value) -> B gets 10.
    assert out.loc[out["company_id"] == "B", "return_on_equity_pct"].iloc[0] == 10.0


def test_impute_sector_median_falls_back_to_global_when_sector_all_nan(toy_big_group=None):
    df = pd.DataFrame(
        {
            "company_id": ["A", "B", "C"],
            "broad_sector": ["Tech", "Energy", "Energy"],
            "return_on_equity_pct": [10.0, np.nan, np.nan],
            "debt_to_equity": [1.0, 1.0, 1.0],
            "revenue_cagr_5yr": [1.0, 1.0, 1.0],
            "fcf_cagr_5yr": [1.0, 1.0, 1.0],
            "operating_profit_margin_pct": [1.0, 1.0, 1.0],
        }
    )
    out = impute_sector_median(df)
    # Energy sector has no non-null ROE at all -> falls back to the
    # global median (10.0, from Tech's single value).
    assert (out.loc[out["broad_sector"] == "Energy", "return_on_equity_pct"] == 10.0).all()


def test_scale_features_zero_mean_unit_variance(toy_df):
    imputed = impute_sector_median(toy_df)
    scaled, scaler = scale_features(imputed)

    assert scaled.shape == (4, len(FEATURES))
    np.testing.assert_allclose(scaled.mean(axis=0), 0.0, atol=1e-8)
    # ddof=0 (population std), matching sklearn's StandardScaler.
    np.testing.assert_allclose(scaled.std(axis=0), 1.0, atol=1e-6)


def test_run_clustering_end_to_end():
    labels_df, inertia_df, profile_df = run_clustering(DB_PATH)

    assert set(labels_df.columns) == {
        "company_id",
        "cluster_id",
        "cluster_name",
        "distance_from_centroid",
    }
    assert labels_df["cluster_id"].nunique() == N_CLUSTERS
    assert labels_df["cluster_id"].between(0, N_CLUSTERS - 1).all()
    assert (labels_df["distance_from_centroid"] >= 0).all()
    assert labels_df["company_id"].is_unique

    assert list(inertia_df["k"]) == list(range(2, 11))
    # Inertia should be non-increasing as k grows.
    assert (inertia_df["inertia"].diff().dropna() <= 1e-6).all()
