"""
peer.py
-------
Peer-group percentile rankings.

Loads peer_groups (11 groups) and computes each company's percentile
rank, within its own peer group, across 10 metrics. Writes the result
to a `peer_percentiles` table in SQLite.
"""

import sqlite3

import pandas as pd

from src.screener.engine import load_screener_data

# The 10 metrics ranked within each peer group, and whether a higher
# raw value is better. D/E is inverted (lower is better -> higher
# percentile).
PEER_METRICS = {
    "ROE": ("return_on_equity_pct", True),
    "ROCE": ("roce_percentage", True),
    "Net Profit Margin": ("net_profit_margin_pct", True),
    "Debt to Equity": ("debt_to_equity", False),
    "Free Cash Flow": ("free_cash_flow_cr", True),
    "PAT CAGR 5yr": ("compounded_profit_growth", True),
    "Revenue CAGR 5yr": ("compounded_sales_growth", True),
    "EPS CAGR 5yr": ("eps_cagr_5yr", True),
    "Interest Coverage": ("interest_coverage", True),
    "Asset Turnover": ("asset_turnover", True),
}

NO_PEER_GROUP_MESSAGE = "No peer group assigned"


def load_peer_groups(db_path):
    """Load peer groups."""
    conn = sqlite3.connect(db_path)
    peer_groups = pd.read_sql(
        "SELECT peer_group_name, company_id, is_benchmark FROM peer_groups",
        conn,
    )
    conn.close()
    return peer_groups


def compute_peer_percentiles(db_path):
    """
    Compute percentile ranks for every (company, metric) pair within
    its peer group.

    Returns a long-format DataFrame with columns:
        company_id, peer_group_name, metric, value, percentile_rank, year

    Companies with no peer group assigned are simply absent from the
    result (see `company_peer_summary` for the "No peer group
    assigned" message path) -- this function itself never raises for
    that case.
    """
    metrics_df = load_screener_data(db_path)
    peer_groups = load_peer_groups(db_path)

    merged = peer_groups.merge(metrics_df, on="company_id", how="left")

    records = []

    for group_name, group in merged.groupby("peer_group_name"):

        for metric_name, (column, higher_is_better) in PEER_METRICS.items():

            if column not in group.columns:
                continue

            values = group[column]

            # D/E: invert so lower D/E => higher percentile
            pct_rank = values.rank(method="average", pct=True) * 100
            if not higher_is_better:
                pct_rank = 100 - pct_rank

            for company_id, value, pct, year in zip(
                group["company_id"], values, pct_rank, group["year"]
            ):
                records.append(
                    {
                        "company_id": company_id,
                        "peer_group_name": group_name,
                        "metric": metric_name,
                        "value": None if pd.isna(value) else float(value),
                        "percentile_rank": None if pd.isna(pct) else round(float(pct), 2),
                        "year": None if pd.isna(year) else int(year),
                    }
                )

    return pd.DataFrame(records)


def write_peer_percentiles_table(db_path, peer_percentiles_df=None):
    """
    (Re)creates the peer_percentiles table and loads it with fresh
    percentile ranks.
    """
    if peer_percentiles_df is None:
        peer_percentiles_df = compute_peer_percentiles(db_path)

    conn = sqlite3.connect(db_path)

    conn.execute("DROP TABLE IF EXISTS peer_percentiles")
    conn.execute("""
        CREATE TABLE peer_percentiles (
            id INTEGER PRIMARY KEY,
            company_id TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            percentile_rank REAL,
            year INTEGER,
            FOREIGN KEY(company_id) REFERENCES companies(company_id)
        )
        """)

    peer_percentiles_df.to_sql("peer_percentiles", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()

    return len(peer_percentiles_df)


def company_peer_summary(company_id, db_path=None, peer_percentiles_df=None):
    """
    Return a company's peer percentile rankings.

    If the company has no peer group assigned, returns the
    NO_PEER_GROUP_MESSAGE string instead of raising an error.
    """
    if peer_percentiles_df is None:
        peer_percentiles_df = compute_peer_percentiles(db_path)

    company_rows = peer_percentiles_df[peer_percentiles_df["company_id"] == company_id]

    if company_rows.empty:
        return NO_PEER_GROUP_MESSAGE

    return company_rows.reset_index(drop=True)


if __name__ == "__main__":
    from pathlib import Path

    db = Path(__file__).resolve().parents[2] / "data" / "nifty100.db"
    n = write_peer_percentiles_table(db)
    print(f"Wrote {n} rows to peer_percentiles")
