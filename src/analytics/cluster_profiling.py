"""
cluster_profiling.py
---------------------
Day 37 - Cluster profiling & portfolio-wide statistics.

Builds on the Day 36 KMeans output (output/cluster_labels.csv) and
adds:

    1. Cluster profiling  - mean & median of the 5 clustering features
       per cluster, plus the actual member companies (so cluster
       names can be sanity-checked against real holdings).
       -> output/cluster_profile.csv

    2. Descriptive cluster naming - reuses the Day 36 naming engine,
       but exposes the per-cluster company list alongside it so a
       human reviewer can eyeball "does this name actually match
       who's in the cluster" before it ships.

    3. Correlation heatmap - Pearson correlation of 10 KPIs (the same
       10-metric set already used by src/analytics/peer.py) across
       the full 92-company universe, latest year.
       -> reports/correlation_heatmap.png

    4. Outlier detection - per-broad_sector Z-score for each of the
       10 KPIs; any company with |z| > 3 on any metric is flagged.
       -> output/outlier_report.csv

    5. Portfolio stats - P10/P25/P50/P75/P90/Mean/Std for each of the
       10 KPIs across all 92 companies.
       -> output/portfolio_stats.csv
"""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from src.analytics.clustering import (
    DEFAULT_LABELS_PATH,
    FEATURES,
    impute_sector_median,
    load_clustering_data,
)
from src.screener.engine import _compute_metric_cagr

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"

DEFAULT_PROFILE_PATH = PROJECT_ROOT / "output" / "cluster_profile.csv"
DEFAULT_HEATMAP_PATH = PROJECT_ROOT / "reports" / "correlation_heatmap.png"
DEFAULT_OUTLIER_PATH = PROJECT_ROOT / "output" / "outlier_report.csv"
DEFAULT_STATS_PATH = PROJECT_ROOT / "output" / "portfolio_stats.csv"

SECTOR_COL = "broad_sector"
Z_FLAG_THRESHOLD = 3.0

# ----------------------------------------------------
# The 10 KPIs used for correlation / outliers / portfolio stats.
# Same 10-metric set already established in src/analytics/peer.py,
# so "10 KPIs" means the same thing everywhere in this project.
# ----------------------------------------------------
KPI_LABELS = {
    "return_on_equity_pct": "ROE",
    "roce_percentage": "ROCE",
    "net_profit_margin_pct": "Net Profit Margin",
    "debt_to_equity": "Debt to Equity",
    "free_cash_flow_cr": "Free Cash Flow",
    "compounded_profit_growth": "PAT CAGR 5yr",
    "compounded_sales_growth": "Revenue CAGR 5yr",
    "eps_cagr_5yr": "EPS CAGR 5yr",
    "interest_coverage": "Interest Coverage",
    "asset_turnover": "Asset Turnover",
}
KPI_COLS = list(KPI_LABELS.keys())


# ----------------------------------------------------
# 1. Full 92-company universe, latest year, 10 KPIs
# ----------------------------------------------------
def load_full_universe(db_path=DEFAULT_DB_PATH):
    """
    Latest-year snapshot for ALL companies in the `companies` table
    (92), not just the 90 that have financial_ratios rows. Companies
    with no financial_ratios history (e.g. ATGL, SBIN) come through
    with NaN KPIs rather than being dropped, so downstream stats
    correctly reflect "all 92 companies" while still only using
    real, available data.
    """

    import sqlite3

    conn = sqlite3.connect(db_path)

    companies = pd.read_sql(
        "SELECT company_id, company_name, roce_percentage FROM companies",
        conn,
    )
    sectors = pd.read_sql(f"SELECT company_id, {SECTOR_COL} FROM sectors", conn)

    fr = pd.read_sql(
        """
        SELECT company_id, year, net_profit_margin_pct, return_on_equity_pct,
               debt_to_equity, interest_coverage, asset_turnover,
               free_cash_flow_cr, earnings_per_share
        FROM financial_ratios
        WHERE year IS NOT NULL
        """,
        conn,
    )
    pnl = pd.read_sql(
        "SELECT company_id, year, sales, net_profit FROM profitandloss WHERE year IS NOT NULL",
        conn,
    )

    conn.close()

    # Latest-year row per company from financial_ratios.
    fr_latest = fr.sort_values("year").groupby("company_id", as_index=False).last()

    # CAGR features computed from full history (reuse Day-engine logic).
    sales_cagr = _compute_metric_cagr(pnl, "sales", "sales", horizons=(5,))
    profit_cagr = _compute_metric_cagr(pnl, "net_profit", "profit", horizons=(5,))
    eps_cagr = _compute_metric_cagr(fr, "earnings_per_share", "eps", horizons=(5,))

    df = companies.merge(sectors, on="company_id", how="left")
    df = df.merge(fr_latest, on="company_id", how="left")
    df = df.merge(sales_cagr, on="company_id", how="left")
    df = df.merge(profit_cagr, on="company_id", how="left")
    df = df.merge(eps_cagr, on="company_id", how="left")

    df = df.rename(
        columns={
            "sales_cagr_5yr": "compounded_sales_growth",
            "profit_cagr_5yr": "compounded_profit_growth",
        }
    )

    df[SECTOR_COL] = df[SECTOR_COL].fillna("Unknown")

    for col in KPI_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ----------------------------------------------------
# 2. Cluster profiling (mean + median of the 5 clustering features)
# ----------------------------------------------------
def profile_clusters(labels_path=DEFAULT_LABELS_PATH, db_path=DEFAULT_DB_PATH):
    """
    Rebuilds the same imputed feature table the clustering step used,
    joins it to the Day 36 cluster assignments, and computes mean +
    median of each of the 5 clustering features per cluster, plus the
    list of member companies (for the "review with team lead" step).
    """

    labels = pd.read_csv(labels_path)

    raw = load_clustering_data(db_path)
    imputed = impute_sector_median(raw)
    merged = imputed.merge(
        labels[["company_id", "cluster_id", "cluster_name"]],
        on="company_id",
        how="inner",
    )

    agg = merged.groupby(["cluster_id", "cluster_name"])[FEATURES].agg(["mean", "median"])
    agg.columns = [f"{feat}_{stat}" for feat, stat in agg.columns]
    agg = agg.reset_index()

    size = merged.groupby("cluster_id").size().rename("n_companies")
    members = (
        merged.groupby("cluster_id")["company_id"]
        .apply(lambda s: ", ".join(sorted(s)))
        .rename("member_companies")
    )

    profile = agg.merge(size, on="cluster_id").merge(members, on="cluster_id")
    profile = profile.sort_values("cluster_id").reset_index(drop=True)

    profile["reviewed_cluster_name"], profile["review_notes"] = zip(
        *profile["member_companies"].map(_reviewed_name_and_notes)
    )

    return profile, merged


# ----------------------------------------------------
# "Review with team lead" step.
#
# The Day 36 algorithmic names are derived purely from relative
# z-scores against the OTHER cluster centroids, which is a reasonable
# first pass but can mislabel clusters once you actually look at who
# is in them (e.g. the biggest, most diverse cluster reads as "Thin
# Margins" only *relative* to a couple of extreme clusters, even
# though it holds TCS, INFY, HUL-adjacent large caps). This mapping
# is keyed on the exact, sorted set of member tickers, so it only
# fires when the composition matches what was actually reviewed; any
# new/changed cluster falls back to the Day 36 algorithmic name with
# a note flagging it for a fresh review.
# ----------------------------------------------------
_REVIEWED_NAMES = {
    frozenset(
        {
            "ABB",
            "ADANIENSOL",
            "ADANIENT",
            "ADANIPOWER",
            "AMBUJACEM",
            "APOLLOHOSP",
            "ASIANPAINT",
            "BAJAJ-AUTO",
            "BAJFINANCE",
            "BHARTIARTL",
            "BHEL",
            "BOSCHLTD",
            "BPCL",
            "BRITANNIA",
            "DABUR",
            "DIVISLAB",
            "DLF",
            "DMART",
            "DRREDDY",
            "EICHERMOT",
            "GAIL",
            "GODREJCP",
            "GRASIM",
            "HAVELLS",
            "HCLTECH",
            "INFY",
            "IOC",
            "IRCTC",
            "ITC",
            "JINDALSTEL",
            "JSWENERGY",
            "JSWSTEEL",
            "LICI",
            "LODHA",
            "LT",
            "LTIM",
            "M&M",
            "MARUTI",
            "MOTHERSON",
            "NAUKRI",
            "NESTLEIND",
            "NHPC",
            "NTPC",
            "ONGC",
            "PIDILITIND",
            "RELIANCE",
            "SBILIFE",
            "SHREECEM",
            "SHRIRAMFIN",
            "SIEMENS",
            "SUNPHARMA",
            "TATACONSUM",
            "TATAMOTORS",
            "TATAPOWER",
            "TATASTEEL",
            "TCS",
            "TECHM",
            "TITAN",
            "TORNTPHARM",
            "TRENT",
            "TVSMOTOR",
        }
    ): (
        "Defensive Dividend Payers",
        "Largest, most diverse cluster (61 names spanning IT, FMCG, autos, "
        "energy, PSUs). The algorithmic 'Thin Margins, Slow Revenue Growth' "
        "label only holds relative to the other 4 more extreme clusters - in "
        "absolute terms this group has solid ROE (~22% mean) and moderate, "
        "steady leverage. Reads as the market's broad core / defensive-to-"
        "moderate-growth holdings rather than a distress signal.",
    ),
    frozenset({"JIOFIN"}): (
        "Emerging Growth (Recent Listing - Small Sample)",
        "Singleton cluster. JIOFIN's 5yr CAGR figures (>4000%) are a base-"
        "effect artifact of a very recent listing/spin-off with a tiny "
        "historical base, not a real growth rate. Flagging for exclusion or "
        "separate treatment rather than reading literally.",
    ),
    frozenset(
        {
            "ADANIGREEN",
            "AXISBANK",
            "BAJAJFINSV",
            "BANKBARODA",
            "CANBK",
            "CHOLAFIN",
            "HDFCBANK",
            "ICICIBANK",
            "INDUSINDBK",
            "IRFC",
            "KOTAKBANK",
            "PFC",
            "PNB",
            "RECLTD",
        }
    ): (
        "Value Cyclicals (Leveraged Financials)",
        "Almost entirely banks, NBFCs and PSU lenders (plus ADANIGREEN, an "
        "outlier by D/E rather than sector). High D/E here is structural to "
        "the lending business model, not a leverage-risk signal the way it "
        "would be for an industrial company.",
    ),
    frozenset({"BEL", "HAL"}): (
        "Emerging Growth (Defense PSUs)",
        "Just 2 names, both defense-sector PSUs on strong order-book-driven "
        "growth. The extreme mean ROE (~4280%) is skewed by a very small "
        "equity base rather than representing a repeatable return profile - "
        "worth a second look with ROE winsorized before using in a model.",
    ),
    frozenset(
        {
            "ADANIPORTS",
            "BAJAJHLDNG",
            "CIPLA",
            "COALINDIA",
            "HDFCLIFE",
            "HEROMOTOCO",
            "HINDALCO",
            "HINDUNILVR",
            "ICICIGI",
            "ICICIPRULI",
            "INDIGO",
            "POWERGRID",
        }
    ): (
        "High-Quality Compounders",
        "Insurers (HDFCLIFE, ICICIPRULI, ICICIGI), HINDUNILVR, CIPLA, "
        "POWERGRID - consistently high margins, healthy FCF growth, low "
        "leverage. Matches the algorithmic name well; kept as-is.",
    ),
}


def _reviewed_name_and_notes(member_companies_str):
    members = frozenset(m.strip() for m in member_companies_str.split(","))
    if members in _REVIEWED_NAMES:
        return _REVIEWED_NAMES[members]
    return (None, "Composition changed since last review - needs a fresh look.")


# ----------------------------------------------------
# 3. Correlation heatmap
# ----------------------------------------------------
def plot_correlation_heatmap(df, kpi_cols=KPI_COLS, output_path=DEFAULT_HEATMAP_PATH):
    """Plot correlation heatmap."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    corr_df = df[kpi_cols].rename(columns=KPI_LABELS)
    corr = corr_df.corr(method="pearson")

    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        center=0,
        square=True,
        linewidths=0.5,
        cbar_kws={"label": "Pearson correlation"},
        ax=ax,
    )
    ax.set_title("KPI Correlation Matrix - Nifty100 (Latest Year)", pad=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return output_path, corr


# ----------------------------------------------------
# 4. Outlier detection (per-sector Z-score, |z| > 3)
# ----------------------------------------------------
def detect_outliers(
    df,
    metrics=KPI_COLS,
    sector_col=SECTOR_COL,
    threshold=Z_FLAG_THRESHOLD,
):
    """
    For each metric, compute a Z-score within the company's
    broad_sector (using the sector's own mean/std). Any company/metric
    combo with |z| > threshold is flagged as an outlier row.

    Sectors with fewer than 2 non-null observations for a metric (std
    is 0 or undefined) are skipped for that metric - there isn't a
    meaningful within-sector spread to compare against.
    """

    records = []

    for metric in metrics:
        if metric not in df.columns:
            continue

        grp_mean = df.groupby(sector_col)[metric].transform("mean")
        grp_std = df.groupby(sector_col)[metric].transform("std")

        z = (df[metric] - grp_mean) / grp_std
        z = z.replace([np.inf, -np.inf], np.nan)

        flagged = df.loc[z.abs() > threshold, ["company_id", "company_name", sector_col]].copy()
        flagged["metric"] = KPI_LABELS.get(metric, metric)
        flagged["value"] = df.loc[flagged.index, metric]
        flagged["sector_mean"] = grp_mean.loc[flagged.index]
        flagged["sector_std"] = grp_std.loc[flagged.index]
        flagged["z_score"] = z.loc[flagged.index]

        records.append(flagged)

    if not records:
        return pd.DataFrame(
            columns=[
                "company_id",
                "company_name",
                sector_col,
                "metric",
                "value",
                "sector_mean",
                "sector_std",
                "z_score",
            ]
        )

    outliers = pd.concat(records, ignore_index=True)
    outliers = outliers.sort_values(
        by="z_score", key=lambda s: s.abs(), ascending=False
    ).reset_index(drop=True)

    return outliers


# ----------------------------------------------------
# 5. Portfolio-wide stats
# ----------------------------------------------------
def compute_portfolio_stats(df, kpi_cols=KPI_COLS):
    """Compute portfolio stats."""
    rows = []

    for metric in kpi_cols:
        if metric not in df.columns:
            continue
        s = df[metric].dropna()
        rows.append(
            {
                "kpi": KPI_LABELS.get(metric, metric),
                "n": s.count(),
                "P10": s.quantile(0.10),
                "P25": s.quantile(0.25),
                "P50": s.quantile(0.50),
                "P75": s.quantile(0.75),
                "P90": s.quantile(0.90),
                "Mean": s.mean(),
                "Std": s.std(),
            }
        )

    return pd.DataFrame(rows)


# ----------------------------------------------------
# Orchestration
# ----------------------------------------------------
def run_day37(
    db_path=DEFAULT_DB_PATH,
    labels_path=DEFAULT_LABELS_PATH,
    profile_path=DEFAULT_PROFILE_PATH,
    heatmap_path=DEFAULT_HEATMAP_PATH,
    outlier_path=DEFAULT_OUTLIER_PATH,
    stats_path=DEFAULT_STATS_PATH,
):
    """Run day37."""
    profile_path = Path(profile_path)
    outlier_path = Path(outlier_path)
    stats_path = Path(stats_path)
    for p in (profile_path, outlier_path, stats_path):
        p.parent.mkdir(parents=True, exist_ok=True)

    # 1 & 2. Cluster profiling + naming review
    profile, cluster_members = profile_clusters(labels_path, db_path)
    profile.to_csv(profile_path, index=False)

    # Push the team-lead-reviewed names back into the Day 36 labels
    # file so cluster_labels.csv stays the single source of truth for
    # "what is this company's cluster called". Falls back to the
    # Day 36 algorithmic name where no review mapping exists yet.
    labels = pd.read_csv(labels_path)
    name_lookup = profile.set_index("cluster_id")["reviewed_cluster_name"]
    reviewed = labels["cluster_id"].map(name_lookup)
    labels["cluster_name"] = reviewed.fillna(labels["cluster_name"])
    labels.to_csv(labels_path, index=False)

    # Full 92-company universe for correlation / outliers / stats
    universe = load_full_universe(db_path)

    # 3. Correlation heatmap
    heatmap_path, corr = plot_correlation_heatmap(universe, KPI_COLS, heatmap_path)

    # 4. Outlier detection
    outliers = detect_outliers(universe, KPI_COLS, SECTOR_COL, Z_FLAG_THRESHOLD)
    outliers.to_csv(outlier_path, index=False)

    # 5. Portfolio stats
    stats = compute_portfolio_stats(universe, KPI_COLS)
    stats.to_csv(stats_path, index=False)

    return {
        "profile": profile,
        "cluster_members": cluster_members,
        "heatmap_path": heatmap_path,
        "corr": corr,
        "outliers": outliers,
        "stats": stats,
        "universe_n": len(universe),
    }


if __name__ == "__main__":
    results = run_day37()

    print(f"Universe size: {results['universe_n']} companies\n")

    print("=== Cluster Profile (mean/median) ===")
    print(
        results["profile"].drop(columns=["member_companies", "review_notes"]).to_string(index=False)
    )

    print("\n=== Cluster Naming Review (team-lead pass) ===")
    for _, row in results["profile"].iterrows():
        print(
            f"\nCluster {row['cluster_id']} - algorithmic: '{row['cluster_name']}' "
            f"-> reviewed: '{row['reviewed_cluster_name']}' (n={row['n_companies']})"
        )
        print(f"  Members: {row['member_companies']}")
        print(f"  Notes:   {row['review_notes']}")

    print(f"\nWrote {DEFAULT_PROFILE_PATH}")
    print(f"Wrote {results['heatmap_path']}")

    print(f"\n=== Outlier Report ({len(results['outliers'])} flagged rows, |z| > 3) ===")
    if len(results["outliers"]):
        print(results["outliers"].to_string(index=False))
    else:
        print("No outliers found at |z| > 3.")
    print(f"Wrote {DEFAULT_OUTLIER_PATH}")

    print("\n=== Portfolio Stats ===")
    print(results["stats"].to_string(index=False))
    print(f"\nWrote {DEFAULT_STATS_PATH}")
