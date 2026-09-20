"""
radar.py
--------
Generates an 8-axis radar (polar) chart per company:
  ROE, ROCE, NPM, D/E, FCF score, PAT CAGR 5yr, Revenue CAGR 5yr,
  Composite Score

Each chart shows the company as a filled polygon, with its peer
group's average as a dashed outline overlay. Companies with no peer
group get a standalone bar comparing them to the Nifty 100 average
instead.

Exports PNG files to reports/radar_charts/{company_id}_radar.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analytics.peer import load_peer_groups
from src.screener.engine import calculate_composite_score, load_screener_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "radar_charts"

RADAR_AXES = [
    ("roe_score", "ROE"),
    ("roce_score", "ROCE"),
    ("npm_score", "NPM"),
    ("de_score", "D/E"),
    ("fcf_cagr_score", "FCF Score"),
    ("pat_cagr_score", "PAT CAGR 5yr"),
    ("revenue_cagr_score", "Revenue CAGR 5yr"),
    ("composite_quality_score", "Composite Score"),
]


def _prepare_scored_data(db_path):
    df = load_screener_data(db_path)
    df = calculate_composite_score(df)
    peer_groups = load_peer_groups(db_path)
    df = df.merge(peer_groups[["company_id", "peer_group_name"]], on="company_id", how="left")
    return df


def _plot_company_radar(company_row, peer_avg, ax_labels, out_path, title):

    n = len(ax_labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    company_values = [company_row[col] for col, _ in RADAR_AXES]
    company_values += company_values[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

    ax.plot(angles, company_values, color="#1F4E78", linewidth=2, label=company_row["company_id"])
    ax.fill(angles, company_values, color="#1F4E78", alpha=0.25)

    if peer_avg is not None:
        peer_values = [peer_avg[col] for col, _ in RADAR_AXES]
        peer_values += peer_values[:1]
        ax.plot(
            angles,
            peer_values,
            color="#C0504D",
            linewidth=1.5,
            linestyle="--",
            label="Peer Group Average",
        )

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(ax_labels, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=7)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _plot_standalone_bar(company_row, universe_avg_score, out_path, title):

    fig, ax = plt.subplots(figsize=(4, 4))

    labels = [company_row["company_id"], "Nifty 100 Average"]
    values = [company_row["composite_quality_score"], universe_avg_score]

    bars = ax.bar(labels, values, color=["#1F4E78", "#C0504D"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Composite Quality Score")
    ax.set_title(title, fontsize=11, fontweight="bold")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1, f"{val:.1f}", ha="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def generate_radar_charts(db_path, output_dir=None):
    """
    Generate one PNG radar chart per company. Returns the list of
    file paths written.
    """
    output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _prepare_scored_data(db_path)
    ax_labels = [label for _, label in RADAR_AXES]
    universe_avg_score = df["composite_quality_score"].mean()

    written = []

    for _, company_row in df.iterrows():

        out_path = output_dir / f"{company_row['company_id']}_radar.png"

        peer_group = company_row.get("peer_group_name")

        if pd.isna(peer_group):
            # No peer group assigned -> standalone chart vs Nifty 100 average
            _plot_standalone_bar(
                company_row,
                universe_avg_score,
                out_path,
                title=f"{company_row['company_id']} vs Nifty 100 Average",
            )
        else:
            peer_rows = df[df["peer_group_name"] == peer_group]
            peer_avg = peer_rows[[col for col, _ in RADAR_AXES]].mean()

            _plot_company_radar(
                company_row,
                peer_avg,
                ax_labels,
                out_path,
                title=f"{company_row['company_id']} vs {peer_group} Peer Average",
            )

        written.append(out_path)

    return written


if __name__ == "__main__":
    paths = generate_radar_charts(PROJECT_ROOT / "data" / "nifty100.db")
    print(f"Wrote {len(paths)} radar charts to {DEFAULT_OUTPUT_DIR}")
