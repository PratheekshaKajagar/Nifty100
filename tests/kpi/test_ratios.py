import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.ratios import *


def test_net_profit_margin():
    assert round(net_profit_margin(100, 500), 2) == 20.00


def test_net_profit_margin_zero_sales():
    assert net_profit_margin(100, 0) is None


def test_operating_profit_margin():
    assert round(operating_profit_margin(50, 250), 2) == 20.00


def test_opm_crosscheck_false():
    assert opm_cross_check(20, 20.5) is False


def test_opm_crosscheck_true():
    assert opm_cross_check(20, 23) is True


def test_roe():
    assert round(roe(100, 200, 300), 2) == 20.00


def test_negative_equity():
    assert roe(100, -100, 50) is None


def test_roce():
    assert round(roce(100, 200, 300, 500), 2) == 10.00


def test_roa():
    assert round(roa(100, 400), 2) == 25.00


def test_zero_assets():
    assert roa(100, 0) is None
