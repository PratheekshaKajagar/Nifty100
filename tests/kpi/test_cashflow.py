import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.cashflow_kpis import *


def test_fcf():
    assert free_cash_flow(100, -40) == 60


def test_fcf_negative():
    assert free_cash_flow(-50, -20) == -70


def test_quality_high():
    assert cfo_quality_score(200, 100) == "High Quality"


def test_quality_moderate():
    assert cfo_quality_score(75, 100) == "Moderate"


def test_quality_low():
    assert cfo_quality_score(20, 100) == "Accrual Risk"


def test_pat_zero():
    assert cfo_quality_score(100, 0) is None


def test_capex():
    value, label = capex_intensity(-50, 1000)

    assert round(value, 2) == 5
    assert label == "Moderate"


def test_fcf_conversion():
    assert fcf_conversion(100, 200) == 50


def test_zero_operating_profit():
    assert fcf_conversion(100, 0) is None


def test_pattern_reinvestor():
    assert capital_allocation_pattern(100, -50, -20) == "Reinvestor"


def test_pattern_distress():
    assert capital_allocation_pattern(-50, 20, 30) == "Distress Signal"


def test_pattern_cash():
    assert capital_allocation_pattern(10, 20, 30) == "Cash Accumulator"
