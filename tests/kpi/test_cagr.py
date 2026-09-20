import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.cagr import *


def test_normal_cagr():

    value, flag = calculate_cagr(100, 200, 5)

    assert round(value, 2) == 14.87
    assert flag == "NORMAL"


def test_decline_to_loss():

    value, flag = calculate_cagr(100, -50, 5)

    assert value is None
    assert flag == "DECLINE_TO_LOSS"


def test_turnaround():

    value, flag = calculate_cagr(-100, 100, 5)

    assert value is None
    assert flag == "TURNAROUND"


def test_both_negative():

    value, flag = calculate_cagr(-100, -50, 5)

    assert value is None
    assert flag == "BOTH_NEGATIVE"


def test_zero_base():

    value, flag = calculate_cagr(0, 100, 5)

    assert value is None
    assert flag == "ZERO_BASE"


def test_invalid_period():

    value, flag = calculate_cagr(100, 200, 0)

    assert value is None
    assert flag == "INVALID_PERIOD"


def test_revenue_wrapper():

    _, flag = revenue_cagr(100, 200, 5)

    assert flag == "NORMAL"


def test_pat_wrapper():

    _, flag = pat_cagr(100, 200, 5)

    assert flag == "NORMAL"


def test_eps_wrapper():

    _, flag = eps_cagr(100, 200, 5)

    assert flag == "NORMAL"


def test_same_values():

    value, flag = calculate_cagr(100, 100, 5)

    assert round(value, 2) == 0
    assert flag == "NORMAL"
