"""Deterministic forecast accuracy metrics for occurred periods."""
from __future__ import annotations
from decimal import Decimal
from .working_capital_service import dec, json_float


def calculate_forecast_accuracy(rows, as_of: str = "2026-06"):
    rows = list(rows)
    eligible = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        period = row.get("period")
        # Accuracy is measured only over occurred periods.  Formula-only callers
        # omit period and remain eligible for unit-level calculations.
        if period is not None and str(period) > as_of:
            continue
        actual, forecast = dec(row.get("actual")), dec(row.get("forecast"))
        if actual is None or forecast is None:
            continue
        eligible.append((actual, forecast))
    if not eligible or sum((abs(actual) for actual, _ in eligible), Decimal(0)) == 0:
        return {"wape": None, "bias": None, "directional_hit_rate": None, "eligible_periods": len(eligible), "status": "not_eligible", "provenance": "calculated"}
    denominator = sum((abs(actual) for actual, _ in eligible), Decimal(0))
    wape = sum((abs(forecast - actual) for actual, forecast in eligible), Decimal(0)) / denominator
    bias = sum((forecast - actual for actual, forecast in eligible), Decimal(0)) / denominator
    hits = sum((1 for actual, forecast in eligible if (forecast - actual == 0) or ((forecast - actual) * actual >= 0)), 0)
    return {"wape": json_float(wape), "bias": json_float(bias), "directional_hit_rate": json_float(Decimal(hits) / Decimal(len(eligible))), "eligible_periods": len(eligible), "status": "eligible", "provenance": "calculated"}


def calculate_accuracy(rows, as_of: str = "2026-06"):
    return calculate_forecast_accuracy(rows, as_of)
