"""
clustering.py
--------------
Day 36 - KMeans clustering of companies into 5 financial-profile
segments.

Features (latest financial year, one row per company):
    return_on_equity_pct
    debt_to_equity
    revenue_cagr_5yr      (-> sales_cagr_5yr from load_screener_data)
    fcf_cagr_5yr
    operating_profit_margin_pct

Pipeline:
    1. Load latest-year metrics via the existing screener loader.
    2. Impute missing values per feature with the SECTOR median
       (falls back to the overall/global median for sectors that
       have no non-null value for a given feature at all).
    3. Standardise features (zero mean, unit variance).
    4. Fit KMeans(n_clusters=5, random_state=42).
    5. Elbow plot (inertia vs k, k=2..10) -> reports/elbow_plot.png
    6. Cluster assignments + centroid distance -> output/cluster_labels.csv
"""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from src.screener.engine import load_screener_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
DEFAULT_ELBOW_PATH = PROJECT_ROOT / "reports" / "elbow_plot.png"
DEFAULT_LABELS_PATH = PROJECT_ROOT / "output" / "cluster_labels.csv"

N_CLUSTERS = 5
RANDOM_STATE = 42

# Raw source column -> clustering feature name.
FEATURE_SOURCE_MAP = {
    "return_on_equity_pct": "return_on_equity_pct",
    "debt_to_equity": "debt_to_equity",
    "revenue_cagr_5yr": "sales_cagr_5yr",
    "fcf_cagr_5yr": "fcf_cagr_5yr",
    "operating_profit_margin_pct": "operating_profit_margin_pct",
}

FEATURES = list(FEATURE_SOURCE_MAP.keys())

SECTOR_COL = "broad_sector"


# ----------------------------------------------------
# Load + prepare the clustering feature table
# ----------------------------------------------------
def load_clustering_data(db_path):
    """
    Latest-year snapshot with one row per company, renamed to the
    Day 36 feature names, plus company_id / company_name / sector
    for downstream imputation and labelling.
    """

    df = load_screener_data(db_path)

    keep_cols = ["company_id", "company_name", SECTOR_COL] + list(FEATURE_SOURCE_MAP.values())
    df = df[keep_cols].copy()

    df = df.rename(columns={v: k for k, v in FEATURE_SOURCE_MAP.items()})

    df[SECTOR_COL] = df[SECTOR_COL].fillna("Unknown")

    return df


def impute_sector_median(df, features=FEATURES, sector_col=SECTOR_COL):
    """
    Impute each feature's missing values with that feature's median
    within the company's sector. If a sector has no non-null values
    for a feature (all-NaN group), fall back to the overall/global
    median for that feature.
    """

    df = df.copy()

    for feature in features:
        global_median = df[feature].median()

        sector_median = df.groupby(sector_col)[feature].transform("median")
        # groupby.transform("median") returns NaN for all-NaN groups,
        # so those still need the global fallback below.
        sector_median = sector_median.fillna(global_median)

        df[feature] = df[feature].fillna(sector_median)

        # Safety net: if global_median itself was NaN (feature
        # entirely missing), there's nothing sensible to impute with;
        # leave as NaN rather than inventing a value.

    return df


# ----------------------------------------------------
# Scaling
# ----------------------------------------------------
def scale_features(df, features=FEATURES):
    """
    StandardScaler-normalise the feature columns (zero mean, unit
    variance). Returns (scaled_matrix, fitted_scaler).
    """

    scaler = StandardScaler()
    scaled = scaler.fit_transform(df[features])

    return scaled, scaler


# ----------------------------------------------------
# Elbow plot
# ----------------------------------------------------
def compute_inertia_curve(scaled_features, k_range=range(2, 11), random_state=RANDOM_STATE):
    """
    Fit KMeans for each k in k_range and return a DataFrame of
    (k, inertia).
    """

    records = []

    for k in k_range:
        model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        model.fit(scaled_features)
        records.append({"k": k, "inertia": model.inertia_})

    return pd.DataFrame(records)


def plot_elbow(inertia_df, output_path=DEFAULT_ELBOW_PATH, highlight_k=N_CLUSTERS):
    """
    Plot inertia vs k and mark the chosen k (k=5) on the curve.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(
        inertia_df["k"],
        inertia_df["inertia"],
        marker="o",
        color="#1F4E78",
        linewidth=2,
    )

    if highlight_k in inertia_df["k"].values:
        highlight_row = inertia_df.loc[inertia_df["k"] == highlight_k].iloc[0]
        ax.scatter(
            [highlight_row["k"]],
            [highlight_row["inertia"]],
            color="#C00000",
            s=120,
            zorder=5,
            label=f"Chosen k = {highlight_k}",
        )
        ax.legend()

    ax.set_title("KMeans Elbow Plot - Inertia vs k")
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Inertia (within-cluster sum of squares)")
    ax.set_xticks(list(inertia_df["k"]))
    ax.grid(True, linestyle="--", alpha=0.4)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path


# ----------------------------------------------------
# Cluster naming
# ----------------------------------------------------
FEATURE_LABELS = {
    "return_on_equity_pct": ("High ROE", "Low ROE"),
    "debt_to_equity": ("High Leverage", "Low Leverage"),
    "revenue_cagr_5yr": ("High Revenue Growth", "Slow Revenue Growth"),
    "fcf_cagr_5yr": ("Strong FCF Growth", "Weak FCF Growth"),
    "operating_profit_margin_pct": ("High Margins", "Thin Margins"),
}

# A few recognisable archetypes, checked in order, based on the sign
# of each feature's z-score (relative to the OTHER cluster centroids).
# +1 = notably high, -1 = notably low, 0 = don't care.
ARCHETYPES = [
    (
        {"return_on_equity_pct": 1, "operating_profit_margin_pct": 1, "debt_to_equity": -1},
        "Quality Compounders",
    ),
    ({"revenue_cagr_5yr": 1, "fcf_cagr_5yr": 1}, "High-Growth Cash Generators"),
    ({"debt_to_equity": 1, "return_on_equity_pct": -1}, "Leveraged Underperformers"),
    (
        {"return_on_equity_pct": -1, "revenue_cagr_5yr": -1, "fcf_cagr_5yr": -1},
        "Low-Growth Laggards",
    ),
    ({"operating_profit_margin_pct": 1, "revenue_cagr_5yr": -1}, "High-Margin Stagnants"),
]

Z_THRESHOLD = 0.4  # min |z| to count as "notably" high/low for archetype matching


def _name_clusters(profile_df):
    """
    Name each cluster from its feature profile relative to the OTHER
    cluster centroids (robust-ish z-score using median/MAD so a single
    outlier-driven cluster doesn't distort the scale for everyone
    else), first trying a small set of recognisable archetypes, then
    falling back to a "High X, Low Y" description built from the two
    most distinctive features. Names are de-duplicated for uniqueness.

    profile_df: index = cluster_id, columns = FEATURES (mean values).
    """

    median = profile_df.median()
    mad = (profile_df - median).abs().median().replace(0, np.nan)
    z = (profile_df - median) / mad
    z = z.fillna(0.0)

    names = {}
    for cluster_id in profile_df.index:
        row_z = z.loc[cluster_id]
        signs = {
            feat: (1 if row_z[feat] > Z_THRESHOLD else (-1 if row_z[feat] < -Z_THRESHOLD else 0))
            for feat in FEATURES
        }

        matched = None
        for pattern, archetype_name in ARCHETYPES:
            if all(signs[feat] == want for feat, want in pattern.items()):
                matched = archetype_name
                break

        if matched:
            names[cluster_id] = matched
            continue

        # Fallback: describe the two most distinctive features.
        ranked_feats = row_z.abs().sort_values(ascending=False).index.tolist()
        descriptors = []
        for feat in ranked_feats:
            if signs[feat] == 0:
                continue
            high_label, low_label = FEATURE_LABELS[feat]
            descriptors.append(high_label if signs[feat] == 1 else low_label)
            if len(descriptors) == 2:
                break

        names[cluster_id] = ", ".join(descriptors) if descriptors else "Balanced / Mixed Profile"

    # Guarantee uniqueness (e.g. two clusters both landing on the same
    # description) by suffixing a counter.
    seen = {}
    for cluster_id, name in names.items():
        seen.setdefault(name, 0)
        seen[name] += 1
        if seen[name] > 1:
            names[cluster_id] = f"{name} ({seen[name]})"

    return names


# ----------------------------------------------------
# Main clustering routine
# ----------------------------------------------------
def run_clustering(db_path=DEFAULT_DB_PATH, n_clusters=N_CLUSTERS, random_state=RANDOM_STATE):
    """
    Runs the full Day 36 pipeline and returns:
        labels_df   -> company_id, cluster_id, cluster_name, distance_from_centroid
        inertia_df  -> k, inertia (k=2..10), for the elbow plot
        profile_df  -> mean feature values per cluster (for context/debugging)
    """

    raw = load_clustering_data(db_path)
    imputed = impute_sector_median(raw)

    scaled, scaler = scale_features(imputed)

    inertia_df = compute_inertia_curve(scaled, range(2, 11), random_state)

    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    cluster_ids = model.fit_predict(scaled)

    # Euclidean distance of each point to its assigned centroid.
    centroids = model.cluster_centers_
    distances = np.linalg.norm(scaled - centroids[cluster_ids], axis=1)

    imputed["cluster_id"] = cluster_ids
    imputed["distance_from_centroid"] = distances

    profile_df = imputed.groupby("cluster_id")[FEATURES].mean()
    cluster_names = _name_clusters(profile_df)
    imputed["cluster_name"] = imputed["cluster_id"].map(cluster_names)

    labels_df = (
        imputed[["company_id", "cluster_id", "cluster_name", "distance_from_centroid"]]
        .sort_values(["cluster_id", "distance_from_centroid"])
        .reset_index(drop=True)
    )

    return labels_df, inertia_df, profile_df


def generate_clustering_outputs(
    db_path=DEFAULT_DB_PATH,
    elbow_path=DEFAULT_ELBOW_PATH,
    labels_path=DEFAULT_LABELS_PATH,
):
    """Generate clustering outputs."""
    labels_df, inertia_df, profile_df = run_clustering(db_path)

    elbow_path = Path(elbow_path)
    labels_path = Path(labels_path)
    labels_path.parent.mkdir(parents=True, exist_ok=True)

    plot_elbow(inertia_df, elbow_path, highlight_k=N_CLUSTERS)
    labels_df.to_csv(labels_path, index=False)

    return elbow_path, labels_path, labels_df, inertia_df, profile_df


if __name__ == "__main__":
    elbow_path, labels_path, labels_df, inertia_df, profile_df = generate_clustering_outputs()

    print(f"Wrote {elbow_path}")
    print(f"Wrote {labels_path} ({len(labels_df)} companies)")
    print("\nCluster sizes:")
    print(labels_df["cluster_name"].value_counts().to_string())
    print("\nInertia by k:")
    print(inertia_df.to_string(index=False))
