"""
tests/dq/test_rules.py
-----------------------
Day 41 - one test per data-quality rule implemented in
src/etl/validator.py (DQ-01 through DQ-14). Each test crafts a
DataFrame that violates exactly that rule and verifies the correct
rule_id and severity come back in the validator's report.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.etl.validator import DataValidator


def _rows_for_rule(report, rule_id):
    return report[report["rule"] == rule_id]


# ----------------------------------------------------
# DQ-01: duplicate primary key
# ----------------------------------------------------
def test_dq01_duplicate_primary_key():
    df = pd.DataFrame({"id": [1, 2, 2], "sales": [10, 20, 20]})

    validator = DataValidator()
    validator.check_primary_key(df, "test", "id")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-01")
    assert len(rows) == 1
    assert (rows["severity"] == "CRITICAL").all()


# ----------------------------------------------------
# DQ-02: missing value
# ----------------------------------------------------
def test_dq02_missing_value():
    df = pd.DataFrame({"id": [1, 2], "sales": [100, None]})

    validator = DataValidator()
    validator.check_missing_values(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-02")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-03: negative numeric value
# ----------------------------------------------------
def test_dq03_negative_numeric():
    df = pd.DataFrame({"id": [1], "sales": [-100]})

    validator = DataValidator()
    validator.check_negative_numeric(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-03")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-04: year outside plausible range
# ----------------------------------------------------
def test_dq04_year_out_of_range():
    df = pd.DataFrame({"id": [1, 2], "year": [2022, 1850]})

    validator = DataValidator()
    validator.check_year_range(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-04")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-05: implausible percentage
# ----------------------------------------------------
def test_dq05_implausible_percentage():
    df = pd.DataFrame({"id": [1, 2], "roe_pct": [15.0, 125000.0]})

    validator = DataValidator()
    validator.check_percentage_bounds(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-05")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-06: fully duplicated row
# ----------------------------------------------------
def test_dq06_fully_duplicated_row():
    df = pd.DataFrame(
        {
            "company_id": ["TCS", "TCS"],
            "sales": [100, 100],
        }
    )

    validator = DataValidator()
    validator.check_duplicate_rows(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-06")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-07: orphan foreign key
# ----------------------------------------------------
def test_dq07_orphan_foreign_key():
    df = pd.DataFrame({"company_id": ["TCS", "GHOST"], "sales": [100, 50]})
    valid_ids = {"TCS", "INFY"}

    validator = DataValidator()
    validator.check_orphan_foreign_key(df, "test", valid_ids)
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-07")
    assert len(rows) == 1
    assert (rows["severity"] == "CRITICAL").all()


# ----------------------------------------------------
# DQ-08: blank / whitespace-only text
# ----------------------------------------------------
def test_dq08_blank_text():
    df = pd.DataFrame({"company_name": ["Tata Consultancy", "   "]})

    validator = DataValidator()
    validator.check_blank_text(df, "test", columns=["company_name"])
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-08")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-09: implausible ratio value
# ----------------------------------------------------
def test_dq09_implausible_ratio():
    df = pd.DataFrame({"debt_to_equity": [0.5, 500.0]})

    validator = DataValidator()
    validator.check_ratio_bounds(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-09")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-10: non-numeric junk token in a numeric-intended column
# ----------------------------------------------------
def test_dq10_non_numeric_junk():
    df = pd.DataFrame({"eps": ["12.5", "#DIV/0!"]})

    validator = DataValidator()
    validator.check_non_numeric_junk(df, "test", columns=["eps"])
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-10")
    assert len(rows) == 1
    assert (rows["severity"] == "CRITICAL").all()


# ----------------------------------------------------
# DQ-11: malformed company_id (whitespace / lower-case)
# ----------------------------------------------------
def test_dq11_malformed_company_id():
    df = pd.DataFrame({"company_id": ["TCS", " infy "]})

    validator = DataValidator()
    validator.check_id_formatting(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-11")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-12: outlier via Z-score
# ----------------------------------------------------
def test_dq12_outlier_zscore():
    # A tight cluster of "normal" values (enough of them that one
    # wild outlier can't drag the std up far enough to hide itself)
    # plus one wild outlier.
    normal = [
        100,
        101,
        99,
        102,
        98,
        100,
        101,
        99,
        100,
        98,
        101,
        99,
        100,
        102,
        98,
        100,
        101,
        99,
        100,
        98,
        101,
        99,
        100,
        102,
        98,
        100,
        101,
        99,
        100,
        98,
    ]
    df = pd.DataFrame({"revenue": normal + [100000]})

    validator = DataValidator()
    validator.check_outlier_zscore(df, "test", columns=["revenue"], threshold=3.0)
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-12")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# DQ-13: required column missing entirely
# ----------------------------------------------------
def test_dq13_required_column_missing():
    df = pd.DataFrame({"company_id": ["TCS"], "sales": [100]})

    validator = DataValidator()
    validator.check_required_columns(df, "test", required_columns=["company_id", "sales", "year"])
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-13")
    assert len(rows) == 1
    assert (rows["severity"] == "CRITICAL").all()
    assert "year" in rows.iloc[0]["message"]


# ----------------------------------------------------
# DQ-14: duplicate (company_id, year) pair
# ----------------------------------------------------
def test_dq14_duplicate_company_year():
    df = pd.DataFrame(
        {
            "company_id": ["TCS", "TCS", "INFY"],
            "year": [2022, 2022, 2022],
            "sales": [100, 105, 90],
        }
    )

    validator = DataValidator()
    validator.check_duplicate_company_year(df, "test")
    report = validator.report()

    rows = _rows_for_rule(report, "DQ-14")
    assert len(rows) == 1
    assert (rows["severity"] == "WARNING").all()


# ----------------------------------------------------
# Sanity check: a fully clean DataFrame passing through the
# whole 14-rule pipeline produces zero failures.
# ----------------------------------------------------
def test_all_rules_clean_dataframe_no_failures():
    df = pd.DataFrame(
        {
            "company_id": ["TCS", "INFY"],
            "year": [2022, 2023],
            "sales": [100.0, 200.0],
            "roe_pct": [18.5, 22.0],
        }
    )

    validator = DataValidator()
    validator.validate(
        "test",
        df,
        valid_company_ids={"TCS", "INFY"},
        required_columns=["company_id", "year", "sales"],
    )
    report = validator.report()

    assert len(report) == 0
