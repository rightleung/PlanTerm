"""Variance aggregation and favorability rules."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from src.models.planning import PlanningRecord, VarianceRow


FAVORABILITY = {
    "revenue": "higher",
    "gross_profit": "higher",
    "operating_profit": "higher",
    "operating_margin": "higher",
    "volume": "higher",
    "average_ticket": "higher",
    "operating_expense": "lower",
}


def safe_pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def status_for(metric: str, variance: float | None, denominator: float | None) -> str | None:
    if variance is None or denominator in (None, 0):
        return None
    pct = variance / abs(denominator)
    if abs(pct) <= 0.01:
        return "Neutral"
    is_favorable = pct > 0 if FAVORABILITY.get(metric, "higher") == "higher" else pct < 0
    return "Favorable" if is_favorable else "Unfavorable"


def aggregate(records: Iterable[PlanningRecord], scenario: str, periods: set[str], metric: str) -> dict[str, float]:
    values: dict[str, float] = defaultdict(float)
    for record in records:
        if record.scenario.value == scenario and record.period in periods and record.metric == metric and record.value is not None:
            values[record.business_unit] += record.value
    return dict(values)


def aggregate_total(records: Iterable[PlanningRecord], scenario: str, periods: set[str], metric: str, units: set[str]) -> float | None:
    values = aggregate(records, scenario, periods, metric)
    selected = [value for name, value in values.items() if name in units]
    return sum(selected) if selected else None


def make_variance_rows(records: tuple[PlanningRecord, ...], units: set[str], ytd_periods: set[str], fy_periods: set[str], pvm_by_unit: dict[str, dict[str, float]]) -> list[VarianceRow]:
    rows: list[VarianceRow] = []
    for unit in sorted(units):
        actual = {metric: aggregate(records, "actual", ytd_periods, metric).get(unit) for metric in ("revenue", "gross_profit", "operating_profit", "operating_expense")}
        budget = {metric: aggregate(records, "budget", ytd_periods, metric).get(unit) for metric in ("revenue", "gross_profit", "operating_profit", "operating_expense")}
        fy_forecast = aggregate(records, "forecast", fy_periods, "revenue").get(unit)
        fy_budget = aggregate(records, "budget", fy_periods, "revenue").get(unit)
        revenue_variance = None if actual["revenue"] is None or budget["revenue"] is None else actual["revenue"] - budget["revenue"]
        pvm = pvm_by_unit.get(unit, {})
        drivers = {"Price": abs(pvm.get("price", 0)), "Volume": abs(pvm.get("volume", 0)), "Mix": abs(pvm.get("mix", 0)), "Opex": abs((actual["operating_expense"] or 0) - (budget["operating_expense"] or 0))}
        primary_driver = max(drivers, key=drivers.get) if drivers and max(drivers.values()) > 0 else None
        brand = "TOP_TOY" if unit == "TOP TOY - Global" else "MINISO"
        market = "global" if brand == "TOP_TOY" else ("mainland" if "Mainland" in unit else "overseas")
        rows.append(VarianceRow(
            business_unit=unit,
            brand=brand,
            market=market,
            revenue_actual=actual["revenue"],
            revenue_budget=budget["revenue"],
            revenue_variance=revenue_variance,
            revenue_variance_pct=safe_pct(revenue_variance, budget["revenue"]),
            gross_profit_actual=actual["gross_profit"],
            gross_profit_budget=budget["gross_profit"],
            operating_profit_actual=actual["operating_profit"],
            operating_profit_budget=budget["operating_profit"],
            operating_margin_actual=safe_pct(actual["operating_profit"], actual["revenue"]),
            operating_margin_budget=safe_pct(budget["operating_profit"], budget["revenue"]),
            operating_expense_actual=actual["operating_expense"],
            operating_expense_budget=budget["operating_expense"],
            forecast_gap=None if fy_forecast is None or fy_budget is None else fy_forecast - fy_budget,
            price_amount=pvm.get("price"),
            volume_amount=pvm.get("volume"),
            mix_amount=pvm.get("mix"),
            primary_driver=primary_driver,
            status=status_for("revenue", revenue_variance, budget["revenue"]),
        ))
    return rows
