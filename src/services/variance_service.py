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


def least_favorable_driver(effects: dict[str, float]) -> str | None:
    """Choose the most adverse signed effect, with deterministic tie handling."""
    if not effects:
        return None
    adverse = {name: amount for name, amount in effects.items() if amount < 0}
    pool = adverse or effects
    return min(pool, key=lambda name: (pool[name], name)) if adverse else max(pool, key=lambda name: (pool[name], name))


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


def calculate_profit_effects(actual: dict[str, float | None], budget: dict[str, float | None], pvm: dict[str, float]) -> dict[str, float]:
    """Build a profit bridge from revenue PVM, gross margin and operating expense."""
    effects: dict[str, float] = {}
    budget_gm = safe_pct(budget.get("gross_profit"), budget.get("revenue"))
    actual_gm = safe_pct(actual.get("gross_profit"), actual.get("revenue"))
    if budget_gm is not None:
        for driver in ("price", "volume", "mix"):
            if pvm.get(driver) is not None:
                effects[driver.title()] = pvm[driver] * budget_gm
    if actual.get("revenue") is not None and actual_gm is not None and budget_gm is not None:
        effects["Gross Margin"] = actual["revenue"] * (actual_gm - budget_gm)
    if actual.get("operating_expense") is not None and budget.get("operating_expense") is not None:
        effects["Opex"] = -(actual["operating_expense"] - budget["operating_expense"])
    return effects


def make_variance_rows(records: tuple[PlanningRecord, ...], units: set[str], ytd_periods: set[str], fy_periods: set[str], pvm_by_unit: dict[str, dict[str, float]]) -> list[VarianceRow]:
    rows: list[VarianceRow] = []
    for unit in sorted(units):
        actual = {metric: aggregate(records, "actual", ytd_periods, metric).get(unit) for metric in ("revenue", "gross_profit", "operating_profit", "operating_expense")}
        budget = {metric: aggregate(records, "budget", ytd_periods, metric).get(unit) for metric in ("revenue", "gross_profit", "operating_profit", "operating_expense")}
        fy_forecast = aggregate(records, "forecast", fy_periods, "revenue").get(unit)
        fy_budget = aggregate(records, "budget", fy_periods, "revenue").get(unit)
        revenue_variance = None if actual["revenue"] is None or budget["revenue"] is None else actual["revenue"] - budget["revenue"]
        operating_profit_variance = None if actual["operating_profit"] is None or budget["operating_profit"] is None else actual["operating_profit"] - budget["operating_profit"]
        gross_margin_actual = safe_pct(actual["gross_profit"], actual["revenue"])
        gross_margin_budget = safe_pct(budget["gross_profit"], budget["revenue"])
        pvm = pvm_by_unit.get(unit, {})
        revenue_drivers = {name: pvm[name] for name in ("price", "volume", "mix") if pvm.get(name) is not None}
        primary_driver_name = least_favorable_driver(revenue_drivers)
        primary_driver = primary_driver_name.title() if primary_driver_name else None
        profit_effects = calculate_profit_effects(actual, budget, pvm)
        if operating_profit_variance is not None and profit_effects and abs(sum(profit_effects.values()) - operating_profit_variance) > 0.01:
            raise ValueError(f"Profit driver reconciliation failed for {unit}")
        profit_driver = least_favorable_driver(profit_effects)
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
            gross_margin_actual=gross_margin_actual,
            gross_margin_budget=gross_margin_budget,
            operating_profit_actual=actual["operating_profit"],
            operating_profit_budget=budget["operating_profit"],
            operating_profit_variance=operating_profit_variance,
            operating_margin_actual=safe_pct(actual["operating_profit"], actual["revenue"]),
            operating_margin_budget=safe_pct(budget["operating_profit"], budget["revenue"]),
            operating_expense_actual=actual["operating_expense"],
            operating_expense_budget=budget["operating_expense"],
            fy_budget=fy_budget,
            fy_forecast=fy_forecast,
            forecast_gap=None if fy_forecast is None or fy_budget is None else fy_forecast - fy_budget,
            price_amount=pvm.get("price"),
            volume_amount=pvm.get("volume"),
            mix_amount=pvm.get("mix"),
            primary_driver=primary_driver,
            profit_driver=profit_driver,
            profit_driver_amount=profit_effects.get(profit_driver) if profit_driver else None,
            status=status_for("revenue", revenue_variance, budget["revenue"]),
        ))
    return rows
