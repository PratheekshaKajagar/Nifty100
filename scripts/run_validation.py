"""
scripts/run_validation.py
----------------------------
Runs the 14-rule DataValidator (src/etl/validator.py) across every
processed source table in data/processed/, and writes
output/validation_failures.csv in the company_id / field / issue /
severity shape the Day 45 acceptance gate (AC-19) expects.

Run with:
    PYTHONPATH=. python3 scripts/run_validation.py
"""

from pathlib import Path

import pandas as pd

from src.etl.validator import DataValidator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUT_PATH = PROJECT_ROOT / "output" / "validation_failures.csv"

# dataset name -> (csv filename, required columns to check for schema drift)
DATASETS = {
    "companies": ("companies.csv", ["company_id", "company_name"]),
    "sectors": ("sectors.csv", ["company_id", "broad_sector", "sub_sector"]),
    "profitandloss": ("profitandloss.csv", ["company_id", "year", "sales", "net_profit"]),
    "balancesheet": ("balancesheet.csv", ["company_id", "year"]),
    "cashflow": ("cashflow.csv", ["company_id", "year"]),
    "financial_ratios": ("financial_ratios.csv", ["company_id", "year"]),
    "market_cap": ("market_cap.csv", ["company_id", "year"]),
    "peer_groups": ("peer_groups.csv", ["company_id", "peer_group_name"]),
    "documents": ("documents.csv", ["company_id", "year"]),
    "prosandcons": ("prosandcons.csv", ["company_id"]),
    "analysis": ("analysis.csv", ["company_id"]),
}


def run():
    companies_df = pd.read_csv(PROCESSED_DIR / "companies.csv")
    valid_company_ids = set(companies_df["company_id"])

    all_failures = []

    for dataset_name, (filename, required_cols) in DATASETS.items():
        path = PROCESSED_DIR / filename
        if not path.exists():
            continue

        df = pd.read_csv(path)
        validator = DataValidator()
        validator.validate(
            dataset_name,
            df,
            valid_company_ids=valid_company_ids,
            required_columns=required_cols,
        )
        report = validator.report()

        for _, row in report.iterrows():
            row_idx = row["row"]
            company_id = None
            field = dataset_name
            if row_idx is not None and "company_id" in df.columns:
                try:
                    company_id = df.loc[row_idx, "company_id"]
                except (KeyError, TypeError):
                    company_id = None

            all_failures.append(
                {
                    "company_id": company_id,
                    "field": field,
                    "issue": f"[{row['rule']}] {row['message']}",
                    "severity": row["severity"],
                }
            )

    result_df = pd.DataFrame(
        all_failures, columns=["company_id", "field", "issue", "severity"]
    )
    OUT_PATH.parent.mkdir(exist_ok=True)
    result_df.to_csv(OUT_PATH, index=False)

    print(f"Wrote {OUT_PATH} ({len(result_df)} rows)")
    if len(result_df):
        print(result_df["severity"].value_counts())
    return result_df


if __name__ == "__main__":
    run()
