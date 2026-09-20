import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parents[2] / "config" / "screener_config.yaml"


# ----------------------------------------------------
# Load YAML Configuration
# ----------------------------------------------------
def load_config():
    """Load config."""
    with open(CONFIG, "r") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------
# CAGR Helpers
# ----------------------------------------------------
def _single_cagr(base_value, latest_value, n_years):
    """
    Safe CAGR calculation.
    Returns NaN when the inputs make CAGR meaningless
    (missing values, non-positive base/latest, or zero years).
    """
    if (
        pd.isna(base_value)
        or pd.isna(latest_value)
        or base_value <= 0
        or latest_value <= 0
        or n_years <= 0
    ):
        return np.nan

    return ((latest_value / base_value) ** (1 / n_years) - 1) * 100


def _compute_metric_cagr(history, value_col, out_prefix, horizons=(3, 5)):
    """
    Generic CAGR computation for any metric that has a full
    (company_id, year, value_col) history table.

    For each company and each horizon N:
      - latest_year = the most recent year available
      - target_year = latest_year - N
      - base_year   = the closest available year <= target_year;
                       if no such year exists (company has less than
                       N years of history), fall back to the earliest
                       available year instead of producing NaN.

    Returns a DataFrame with columns:
      company_id, {out_prefix}_cagr_{N}yr  (one per horizon)
    """
    records = []

    for company_id, group in history.groupby("company_id"):

        group = group.dropna(subset=["year"]).sort_values("year")

        if group.empty:
            continue

        latest_row = group.iloc[-1]
        latest_year = latest_row["year"]

        record = {"company_id": company_id}

        for years_back in horizons:

            target_year = latest_year - years_back
            candidates = group[group["year"] <= target_year]

            if not candidates.empty:
                base_row = candidates.iloc[-1]
            else:
                base_row = group.iloc[0]

            n_years = latest_year - base_row["year"]

            record[f"{out_prefix}_cagr_{years_back}yr"] = _single_cagr(
                base_row[value_col], latest_row[value_col], n_years
            )

        records.append(record)

    return pd.DataFrame(records)


# ----------------------------------------------------
# Load Screener Data
# ----------------------------------------------------
def load_screener_data(db_path):
    """
    Load all data required for the screener: latest-year financial
    ratios plus derived CAGR / trend / cash-quality features computed
    from full historical tables (never from the incomplete `analysis`
    table, which only covers 4 companies).
    """

    conn = sqlite3.connect(db_path)

    query = """
    SELECT

        fr.company_id,
        c.company_name,
        c.roce_percentage,
        fr.year,

        s.broad_sector,

        fr.return_on_equity_pct,
        fr.net_profit_margin_pct,
        fr.operating_profit_margin_pct,
        fr.debt_to_equity,
        fr.interest_coverage,
        fr.asset_turnover,
        fr.free_cash_flow_cr,
        fr.cash_from_operations_cr,
        fr.dividend_payout_ratio_pct,
        fr.earnings_per_share,

        mc.market_cap_crore,
        mc.pe_ratio,
        mc.pb_ratio,
        mc.dividend_yield_pct,

        p.sales,
        p.net_profit

    FROM financial_ratios fr

    LEFT JOIN companies c
        ON fr.company_id = c.company_id

    LEFT JOIN sectors s
        ON fr.company_id = s.company_id

    LEFT JOIN market_cap mc
        ON fr.company_id = mc.company_id
        AND fr.year = mc.year

    LEFT JOIN profitandloss p
        ON fr.company_id = p.company_id
        AND fr.year = p.year

    ORDER BY
        fr.company_id,
        fr.year
    """

    df = pd.read_sql(query, conn)

    # -----------------------------
    # Full histories (load BEFORE closing the connection)
    # -----------------------------
    pnl_history = pd.read_sql(
        """
        SELECT company_id, year, sales, net_profit
        FROM profitandloss
        WHERE year IS NOT NULL
        """,
        conn,
    )

    fr_history = pd.read_sql(
        """
        SELECT
            company_id, year,
            free_cash_flow_cr,
            earnings_per_share,
            debt_to_equity
        FROM financial_ratios
        WHERE year IS NOT NULL
        """,
        conn,
    )

    conn.close()

    # -----------------------------
    # CAGR features (3yr + 5yr) computed from full history
    # -----------------------------
    sales_cagr = _compute_metric_cagr(pnl_history, "sales", "sales", horizons=(3, 5))
    profit_cagr = _compute_metric_cagr(pnl_history, "net_profit", "profit", horizons=(3, 5))
    eps_cagr = _compute_metric_cagr(fr_history, "earnings_per_share", "eps", horizons=(5,))
    fcf_cagr = _compute_metric_cagr(fr_history, "free_cash_flow_cr", "fcf", horizons=(5,))

    for cagr_df in (sales_cagr, profit_cagr, eps_cagr, fcf_cagr):
        df = df.merge(cagr_df, on="company_id", how="left")

    # Keep backward-compatible column names used by existing filter
    # presets / tests: "compounded_sales_growth" == sales 5yr CAGR, etc.
    df["compounded_sales_growth"] = df.get("sales_cagr_5yr")
    df["compounded_profit_growth"] = df.get("profit_cagr_5yr")
    df["compounded_sales_growth_3yr"] = df.get("sales_cagr_3yr")
    df["compounded_profit_growth_3yr"] = df.get("profit_cagr_3yr")
    df["eps_cagr_5yr"] = df.get("eps_cagr_5yr")

    # -----------------------------
    # Debt/Equity trend (declining YoY) - "Turnaround Watch" needs this
    # -----------------------------
    de_trend_records = []
    for company_id, group in fr_history.dropna(subset=["year"]).groupby("company_id"):
        group = group.sort_values("year")
        if len(group) < 2:
            de_declining = np.nan
        else:
            latest_de = group.iloc[-1]["debt_to_equity"]
            prev_de = group.iloc[-2]["debt_to_equity"]
            if pd.isna(latest_de) or pd.isna(prev_de):
                de_declining = np.nan
            else:
                de_declining = bool(latest_de < prev_de)
        de_trend_records.append({"company_id": company_id, "de_declining_yoy": de_declining})

    de_trend = pd.DataFrame(de_trend_records)
    df = df.merge(de_trend, on="company_id", how="left")

    # -----------------------------
    # Numeric Columns
    # -----------------------------
    numeric_columns = [
        "year",
        "roce_percentage",
        "return_on_equity_pct",
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "debt_to_equity",
        "interest_coverage",
        "asset_turnover",
        "free_cash_flow_cr",
        "cash_from_operations_cr",
        "dividend_payout_ratio_pct",
        "earnings_per_share",
        "market_cap_crore",
        "pe_ratio",
        "pb_ratio",
        "dividend_yield_pct",
        "sales",
        "net_profit",
        "compounded_sales_growth",
        "compounded_profit_growth",
        "compounded_sales_growth_3yr",
        "compounded_profit_growth_3yr",
        "eps_cagr_5yr",
        "fcf_cagr_5yr",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # -----------------------------
    # Keep Latest Financial Year per company
    # -----------------------------
    df = df.sort_values("year").groupby("company_id", as_index=False).last()

    # -----------------------------
    # Cash-quality features (need latest-year values only, so computed
    # after collapsing to one row per company)
    # -----------------------------
    df["fcf_positive_latest"] = df["free_cash_flow_cr"] > 0

    df["cfo_pat_ratio"] = np.where(
        (df["net_profit"].notna()) & (df["net_profit"] != 0),
        df["cash_from_operations_cr"] / df["net_profit"],
        np.nan,
    )

    return df


# ----------------------------------------------------
# Filter Map
# ----------------------------------------------------
# Covers all 15 metrics required by the Sprint 3 spec, plus a few
# extras (3yr CAGR variants, dividend payout) that the existing
# presets already rely on.
FILTER_MAP = {
    "roe_min": "return_on_equity_pct",
    "debt_to_equity_max": "debt_to_equity",
    "free_cash_flow_min": "free_cash_flow_cr",
    "revenue_cagr_5yr_min": "compounded_sales_growth",
    "pat_cagr_5yr_min": "compounded_profit_growth",
    "revenue_cagr_3yr_min": "compounded_sales_growth_3yr",
    "pat_cagr_3yr_min": "compounded_profit_growth_3yr",
    "opm_min": "operating_profit_margin_pct",
    "pe_max": "pe_ratio",
    "pb_max": "pb_ratio",
    "dividend_yield_min": "dividend_yield_pct",
    "dividend_payout_max": "dividend_payout_ratio_pct",
    "icr_min": "interest_coverage",
    "market_cap_min": "market_cap_crore",
    "net_profit_min": "net_profit",
    "eps_cagr_min": "eps_cagr_5yr",
    "asset_turnover_min": "asset_turnover",
    "sales_min": "sales",
}


# ----------------------------------------------------
# Apply Filters
# ----------------------------------------------------
def apply_filters(df, preset):
    """Apply filters."""
    config = load_config()

    if preset not in config:
        raise ValueError(f"Preset '{preset}' not found.")

    rules = config[preset]

    filtered = df.copy()

    for rule, threshold in rules.items():

        # -------------------------------------------------
        # Special boolean rule: D/E declining year-over-year
        # (used by 'turnaround_watch'). Not a min/max threshold,
        # so it's handled outside FILTER_MAP.
        # -------------------------------------------------
        if rule == "de_declining_yoy":
            if threshold:
                # Tri-state True/False/NaN column, not a plain bool -
                # `== True` (rather than truthiness) is intentional so NaN
                # rows are excluded instead of raising/being ambiguous.
                filtered = filtered[filtered["de_declining_yoy"] == True]  # noqa: E712
            continue

        column = FILTER_MAP.get(rule)

        if column is None:
            continue

        # Minimum Filters
        if rule.endswith("_min"):

            if rule == "icr_min":

                # interest_coverage is NULL/NaN for debt-free companies
                # (see src/analytics/ratios.py: interest_coverage()
                # returns None when interest == 0). Treat a debt-free
                # company's ICR as effectively infinite, so it always
                # passes an ICR minimum threshold.
                filtered = filtered[(filtered[column] >= threshold) | (filtered[column].isna())]

            else:

                filtered = filtered[filtered[column] >= threshold]

        # Maximum Filters
        elif rule.endswith("_max"):

            if rule == "debt_to_equity_max":

                filtered = filtered[
                    (filtered["broad_sector"].str.lower().eq("financials"))
                    | (filtered[column] <= threshold)
                ]

            else:

                filtered = filtered[filtered[column] <= threshold]

        # Exact-value filters (e.g. debt_to_equity_max: 0 already
        # covered above via "_max"; kept here for rules with neither
        # suffix, e.g. a future "sector_eq" style rule)
        else:
            filtered = filtered[filtered[column] == threshold]

    return filtered.reset_index(drop=True)


# ----------------------------------------------------
# Winsorized 0-100 Scoring
# ----------------------------------------------------
def _winsorized_score(series, higher_is_better=True, lower_q=0.10, upper_q=0.90):
    """
    Normalise a metric to a 0-100 scale using P10/P90 winsorisation:
    clip extreme values at the 10th/90th percentile *before* scaling,
    so a handful of outliers can't blow out the whole distribution.

    Returns NaN only where the input itself was NaN; callers decide
    how to handle missing data (see calculate_composite_score, which
    fills missing component scores with a neutral 50 rather than
    letting a single missing metric collapse the whole composite
    score to NaN for that company - this is exactly the bug the
    original 'analysis' table join caused).
    """
    lower = series.quantile(lower_q)
    upper = series.quantile(upper_q)

    clipped = series.clip(lower, upper)

    if pd.isna(upper) or pd.isna(lower) or upper == lower:
        # No spread to score against (e.g. all values equal / all NaN)
        return pd.Series(
            np.where(series.notna(), 100.0, np.nan),
            index=series.index,
        )

    if higher_is_better:
        score = (clipped - lower) / (upper - lower) * 100
    else:
        score = (upper - clipped) / (upper - lower) * 100

    return score


def _score_components(df, group_col=None):
    """
    Compute every weighted sub-component of the composite quality
    score. If group_col is provided, winsorisation quantiles are
    computed within each group (used for the sector-relative score);
    otherwise they're computed across the whole universe.
    """
    scored = df.copy()

    def scored_col(col, higher_is_better=True):
        """Scored col."""
        if group_col is None:
            return _winsorized_score(scored[col], higher_is_better)
        return scored.groupby(group_col, dropna=False)[col].transform(
            lambda s: _winsorized_score(s, higher_is_better)
        )

    components = {}

    # ---- Profitability (35%) ----
    components["roe_score"] = scored_col("return_on_equity_pct")
    components["roce_score"] = scored_col("roce_percentage")
    components["npm_score"] = scored_col("net_profit_margin_pct")

    # ---- Cash Quality (30%) ----
    components["fcf_cagr_score"] = scored_col("fcf_cagr_5yr")
    components["cfo_pat_score"] = scored_col("cfo_pat_ratio")
    components["fcf_positive_score"] = scored["fcf_positive_latest"].map({True: 100.0, False: 0.0})

    # ---- Growth (20%) ----
    components["revenue_cagr_score"] = scored_col("compounded_sales_growth")
    components["pat_cagr_score"] = scored_col("compounded_profit_growth")

    # ---- Leverage (15%) ----
    components["de_score"] = scored_col("debt_to_equity", higher_is_better=False)

    # ICR: NaN means debt-free -> best possible score (infinite ICR)
    icr_score = scored_col("interest_coverage")
    icr_score = icr_score.where(scored["interest_coverage"].notna(), 100.0)
    components["icr_score"] = icr_score

    return pd.DataFrame(components, index=scored.index)


WEIGHTS = {
    "roe_score": 0.15,
    "roce_score": 0.10,
    "npm_score": 0.10,
    "fcf_cagr_score": 0.15,
    "cfo_pat_score": 0.10,
    "fcf_positive_score": 0.05,
    "revenue_cagr_score": 0.10,
    "pat_cagr_score": 0.10,
    "de_score": 0.10,
    "icr_score": 0.05,
}


def calculate_composite_score(df):
    """
    Composite Quality Score (0-100):
      35% Profitability  = ROE 15% + ROCE 10% + NPM 10%
      30% Cash Quality    = FCF CAGR 15% + CFO/PAT 10% + FCF-positive flag 5%
      20% Growth          = Revenue CAGR 10% + PAT CAGR 10%
      15% Leverage         = D/E score 10% + ICR score 5%

    Each metric is normalised with P10/P90 winsorisation before
    weighting. A company missing one underlying metric gets a
    neutral 50 for that component (instead of the whole composite
    score collapsing to NaN, which was the root cause of the
    original screener bug).
    """
    scored = df.copy()

    components = _score_components(scored)

    # Missing data -> neutral score for that one component, not NaN
    # for the whole company.
    components = components.fillna(50.0)

    for col in components.columns:
        scored[col] = components[col]

    scored["composite_quality_score"] = sum(
        components[col] * weight for col, weight in WEIGHTS.items()
    )

    # -----------------------------------------------------------
    # Sector-relative composite score: same formula, but winsorised
    # quantiles are computed within each broad_sector so the score
    # reflects performance vs. sector peers rather than the whole
    # universe.
    # -----------------------------------------------------------
    sector_components = _score_components(scored, group_col="broad_sector")
    sector_components = sector_components.fillna(50.0)

    scored["sector_relative_composite_score"] = sum(
        sector_components[col] * weight for col, weight in WEIGHTS.items()
    )

    # Backward-compatible alias (older code/tests may reference
    # "composite_score").
    scored["composite_score"] = scored["composite_quality_score"]

    return scored


# ----------------------------------------------------
# Sector Ranking
# ----------------------------------------------------
def calculate_sector_percentile(df):
    """
    Calculate sector-wise rankings and percentiles based on the
    composite quality score.
    """

    ranked = df.copy()

    # dropna=False: don't silently drop companies with a missing
    # broad_sector from ranking (pandas groupby drops NaN groups by
    # default).
    ranked["sector_percentile"] = (
        ranked.groupby("broad_sector", dropna=False)["composite_quality_score"].rank(
            method="average", pct=True
        )
        * 100
    )

    # Int64 (nullable) rather than int: composite_quality_score can
    # in principle be NaN for a company with zero usable inputs, and
    # .astype(int) would raise on NaN.
    ranked["sector_rank"] = (
        ranked.groupby("broad_sector", dropna=False)["composite_quality_score"]
        .rank(method="dense", ascending=False)
        .astype("Int64")
    )

    ranked["overall_rank"] = (
        ranked["composite_quality_score"].rank(method="dense", ascending=False).astype("Int64")
    )

    return ranked


# ----------------------------------------------------
# Run Screener
# ----------------------------------------------------
def run_screener(preset, db_path):
    """Run screener."""
    df = load_screener_data(db_path)

    df = calculate_composite_score(df)

    df = calculate_sector_percentile(df)

    result = apply_filters(df, preset)

    result = result.sort_values(by="composite_quality_score", ascending=False)

    return result.reset_index(drop=True)


def run_all_presets(db_path):
    """
    Run every preset defined in screener_config.yaml.
    Returns {preset_name: DataFrame}.
    """
    config = load_config()
    return {preset: run_screener(preset, db_path) for preset in config}
