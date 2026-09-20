import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(PROJECT_ROOT))
import pandas as pd

from src.etl.validator import DataValidator


def test_validator_creation():

    validator = DataValidator()

    assert validator is not None


def test_primary_key_duplicates():

    df = pd.DataFrame({"id": [1, 2, 2]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert len(report) > 0


def test_missing_values():

    df = pd.DataFrame({"id": [1, 2], "sales": [100, None]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-02" in report["rule"].values


def test_negative_values():

    df = pd.DataFrame({"id": [1], "sales": [-100]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-03" in report["rule"].values


def test_clean_dataframe():

    df = pd.DataFrame({"id": [1, 2], "sales": [100, 200]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert isinstance(report, pd.DataFrame)


def test_duplicate_detection():

    df = pd.DataFrame({"id": [5, 5, 6]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert len(report) >= 1


def test_report_columns():

    validator = DataValidator()

    report = validator.report()

    expected = ["dataset", "rule", "severity", "row", "message"]

    for col in expected:
        assert col in report.columns or report.empty


def test_multiple_failures():

    df = pd.DataFrame({"id": [1, 1], "sales": [-100, None]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert len(report) >= 2


def test_year_out_of_range_detected():

    df = pd.DataFrame({"id": [1, 2], "year": [2021, 1850]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-04" in report["rule"].values


def test_year_in_range_passes():

    df = pd.DataFrame({"id": [1, 2], "year": [2020, 2023]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-04" not in report["rule"].values


def test_implausible_percentage_detected():

    df = pd.DataFrame({"id": [1], "return_on_equity_pct": [125000]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-05" in report["rule"].values


def test_plausible_percentage_passes():

    df = pd.DataFrame({"id": [1], "return_on_equity_pct": [18.5]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-05" not in report["rule"].values


def test_full_row_duplicate_detected():

    df = pd.DataFrame({"id": [1, 1], "sales": [100, 100]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-06" in report["rule"].values


def test_no_full_row_duplicate_passes():

    df = pd.DataFrame({"id": [1, 2], "sales": [100, 200]})

    validator = DataValidator()

    validator.validate("test", df)

    report = validator.report()

    assert "DQ-06" not in report["rule"].values
