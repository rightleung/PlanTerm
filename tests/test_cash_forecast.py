from src.services.cash_forecast_service import calculate_cash_bridge
import pytest


def test_cash_bridge_formula_vector():
    row = calculate_cash_bridge({"operating_profit": 10, "prior_ar": 20, "current_ar": 25, "prior_inventory": 30, "current_inventory": 35, "current_ap": 15, "prior_ap": 12, "capex": 4, "other_cash_items": 1, "opening_cash": 100, "minimum_cash_buffer": 80})
    assert row["net_cash_change"] == 0
    assert row["closing_illustrative_cash"] == 100
    assert row["headroom"] == 20


def test_cash_bridge_missing_is_null():
    row = calculate_cash_bridge({"operating_profit": 10})
    assert row["status"] == "not_eligible"
    assert row["closing_illustrative_cash"] is None


def test_cash_bridge_huge_decimal_is_rejected():
    with pytest.raises(ValueError):
        calculate_cash_bridge({"operating_profit": "1e10000", "prior_ar": 1, "current_ar": 1, "prior_inventory": 1, "current_inventory": 1, "current_ap": 1, "prior_ap": 1, "capex": 1, "other_cash_items": 1, "opening_cash": 1, "minimum_cash_buffer": 1})
