import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.ratios import *


def test_debt_to_equity():
    assert debt_to_equity(100, 200, 300) == 0.2


def test_debt_free():
    assert debt_to_equity(0, 200, 300) == 0


def test_negative_equity():
    assert debt_to_equity(100, -200, 100) is None


def test_high_leverage():
    assert high_leverage_flag(6, "Industrials") is True


def test_financial_company():
    assert high_leverage_flag(8, "Financials") is False


def test_interest_coverage():
    assert interest_coverage(120, 30, 10) == 15


def test_interest_zero():
    assert interest_coverage(120, 30, 0) is None


def test_icr_label():
    assert icr_label(None) == "Debt Free"


def test_icr_warning():
    assert icr_warning(1.2) is True


def test_net_debt():
    assert net_debt(500, 200) == 300


def test_asset_turnover():
    assert asset_turnover(1000, 500) == 2


def test_zero_assets():
    assert asset_turnover(1000, 0) is None


def test_bank_not_flagged():

    assert high_leverage_flag(10, "Banks") is False


def test_nbfc_not_flagged():

    assert high_leverage_flag(8, "NBFC") is False


def test_insurance_not_flagged():

    assert high_leverage_flag(7, "Insurance") is False
