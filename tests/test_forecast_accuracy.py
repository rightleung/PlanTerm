from src.services.forecast_accuracy_service import calculate_forecast_accuracy


def test_accuracy_formula_vector():
    result = calculate_forecast_accuracy([{"actual": 100, "forecast": 110}, {"actual": 200, "forecast": 180}])
    assert result["wape"] == 0.1
    assert result["bias"] == -1 / 30
    assert result["directional_hit_rate"] == 0.5


def test_accuracy_zero_denominator_is_null():
    result = calculate_forecast_accuracy([{"actual": 0, "forecast": 1}])
    assert result["status"] == "not_eligible"
    assert result["wape"] is None


def test_accuracy_excludes_future_periods_and_future_only_is_not_eligible():
    result = calculate_forecast_accuracy([{"period": "2026-07", "actual": 100, "forecast": 110}])
    assert result["status"] == "not_eligible"
    assert result["eligible_periods"] == 0
