import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.etl.loader import load_all_excels, load_excel

RAW_DIR = PROJECT_ROOT / "data" / "raw"


def test_load_excel_returns_dataframe():

    file = RAW_DIR / "companies.xlsx"

    df = load_excel(file)

    assert isinstance(df, pd.DataFrame)


def test_load_excel_not_empty():

    file = RAW_DIR / "companies.xlsx"

    df = load_excel(file)

    assert len(df) > 0


def test_company_column_exists():

    file = RAW_DIR / "companies.xlsx"

    df = load_excel(file)

    assert "company_name" in [c.lower() for c in df.columns]


def test_load_all_excels():

    datasets = load_all_excels(RAW_DIR)

    assert isinstance(datasets, dict)


def test_total_datasets_loaded():

    datasets = load_all_excels(RAW_DIR)

    assert len(datasets) == 12


def test_companies_dataset_present():

    datasets = load_all_excels(RAW_DIR)

    assert "companies" in datasets


def test_profit_dataset_present():

    datasets = load_all_excels(RAW_DIR)

    assert "profitandloss" in datasets


def test_stock_prices_present():

    datasets = load_all_excels(RAW_DIR)

    assert "stock_prices" in datasets
