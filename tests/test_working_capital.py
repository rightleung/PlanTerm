from decimal import Decimal

from src.services.working_capital_service import calculate_working_capital
import pytest


def test_working_capital_formula_vector():
    row = calculate_working_capital({"revenue": Decimal("100"), "cogs": Decimal("60"), "ar_days": Decimal("18"), "inventory_days": Decimal("48"), "ap_days": Decimal("35")})
    assert row["ar_balance"] == 100 * 18 / 365
    assert row["inventory_balance"] == 60 * 48 / 365
    assert row["ap_balance"] == 60 * 35 / 365
    assert row["ccc"] == 31
    assert row["nwc"] == row["ar_balance"] + row["inventory_balance"] - row["ap_balance"]


def test_working_capital_missing_is_null():
    row = calculate_working_capital({"revenue": 100, "cogs": None, "ar_days": 18, "inventory_days": 48, "ap_days": 35})
    assert row["status"] == "not_eligible"
    assert row["nwc"] is None


def test_working_capital_huge_decimal_is_rejected():
    with pytest.raises(ValueError):
        calculate_working_capital({"revenue": "1e10000", "cogs": 1, "ar_days": 1, "inventory_days": 1, "ap_days": 1})
