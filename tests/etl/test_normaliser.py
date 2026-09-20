import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.etl.normaliser import (
    normalize_column_names,
    normalize_company_id,
    normalize_dataframe,
    normalize_numeric_columns,
    normalize_year,
)


def test_normalize_column_names():

    df = pd.DataFrame(columns=["Company Name", "Book Value %"])

    df = normalize_column_names(df)

    assert "company_name" in df.columns
    assert "book_value_pct" in df.columns


def test_normalize_company_id():

    df = pd.DataFrame({"company_id": [" abb ", " tcs ", "hdfcbank"]})

    df = normalize_company_id(df)

    assert df["company_id"].tolist() == ["ABB", "TCS", "HDFCBANK"]


def test_normalize_year():

    df = pd.DataFrame({"year": ["Mar 2020", "Dec 2021", "2022"]})

    df = normalize_year(df)

    assert df["year"].tolist() == [2020, 2021, 2022]


def test_normalize_numeric_columns():

    df = pd.DataFrame({"sales": ["1,250", "500", "100"]})

    result = normalize_numeric_columns(df.copy())

    assert result["sales"].dtype.kind in ("i", "f")

    assert result["sales"].tolist() == [1250, 500, 100]


def test_normalize_dataframe():

    df = pd.DataFrame({"Company ID": [" abb "], "Year": ["Mar 2022"], "Sales": ["1,500"]})

    result = normalize_dataframe("profitandloss", df.copy())

    assert result.loc[0, "company_id"] == "ABB"

    assert result.loc[0, "year"] == 2022

    assert result.loc[0, "sales"] == 1500
