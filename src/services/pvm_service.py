"""Price / Volume / Mix bridge using the documented bridge formula."""

from __future__ import annotations

from collections import defaultdict

from src.models.planning import PlanningRecord, PvmBridge


def _values(records: tuple[PlanningRecord, ...], scenario: str, periods: set[str], metric: str, units: set[str]) -> dict[str, float]:
    result: dict[str, float] = defaultdict(float)
    ticket_values: dict[str, list[float]] = defaultdict(list)
    for record in records:
        if record.scenario.value == scenario and record.period in periods and record.metric == metric and record.business_unit in units and record.value is not None:
            if metric == "average_ticket":
                ticket_values[record.business_unit].append(record.value)
            else:
                result[record.business_unit] += record.value
    if metric == "average_ticket":
        return {unit: sum(values) / len(values) for unit, values in ticket_values.items() if values}
    return dict(result)


def calculate_pvm(records: tuple[PlanningRecord, ...], units: set[str], periods: set[str]) -> tuple[PvmBridge, dict[str, dict[str, float]]]:
    actual_revenue = _values(records, "actual", periods, "revenue", units)
    budget_revenue = _values(records, "budget", periods, "revenue", units)
    actual_volume = _values(records, "actual", periods, "volume", units)
    budget_volume = _values(records, "budget", periods, "volume", units)
    actual_ticket = _values(records, "actual", periods, "average_ticket", units)
    budget_ticket = _values(records, "budget", periods, "average_ticket", units)
    total_actual = sum(actual_revenue.values())
    total_budget = sum(budget_revenue.values())
    total_actual_volume = sum(actual_volume.values())
    total_budget_volume = sum(budget_volume.values())
    budget_weighted_ticket = total_budget / total_budget_volume if total_budget_volume else None
    if budget_weighted_ticket is None:
        bridge = PvmBridge(actual_revenue=total_actual or None, budget_revenue=total_budget or None, volume=None, mix=None, price=None, reconciliation_difference=None)
        return bridge, {}

    volume = (total_actual_volume - total_budget_volume) * budget_weighted_ticket
    mix = sum((actual_volume.get(unit, 0) - budget_volume.get(unit, 0)) * (budget_ticket.get(unit, 0) - budget_weighted_ticket) for unit in units)
    price = sum(actual_volume.get(unit, 0) * (actual_ticket.get(unit, 0) - budget_ticket.get(unit, 0)) for unit in units)
    difference = volume + mix + price - (total_actual - total_budget)
    by_unit = {}
    for unit in units:
        by_unit[unit] = {
            "volume": (actual_volume.get(unit, 0) - budget_volume.get(unit, 0)) * budget_ticket.get(unit, 0),
            "price": actual_volume.get(unit, 0) * (actual_ticket.get(unit, 0) - budget_ticket.get(unit, 0)),
            "mix": 0.0,
        }
    return PvmBridge(
        actual_revenue=total_actual,
        budget_revenue=total_budget,
        volume=volume,
        mix=mix,
        price=price,
        reconciliation_difference=difference,
    ), by_unit
