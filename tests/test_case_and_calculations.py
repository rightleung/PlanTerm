import math
from collections import defaultdict

from scripts.build_miniso_case import build_rows
from src.models.planning import PlanningRecord
from src.services.case_builder import validate_case_records
from src.services.pvm_service import calculate_pvm
from src.services.variance_service import calculate_profit_effects, safe_pct, status_for


def test_case_builder_is_repeatable_and_validates_records():
    first = build_rows()
    second = build_rows()
    assert first == second
    # This assertion ensures the shared validator sees the full required metric set.
    validate_case_records([PlanningRecord(period="2026-01", scenario="actual", brand="MINISO", market="mainland", business_unit="MINISO - Chinese Mainland", metric=metric, value=value, unit="RMB millions", provenance="calculated") for metric, value in {"revenue": 10.0, "volume": 2.0, "average_ticket": 5.0, "cost_of_sales": 6.0, "gross_profit": 4.0, "operating_expense": 3.0, "operating_profit": 1.0}.items()])


def test_case_reconciles_group_and_profit_formulas(case):
    actual_h1 = sum(record.value or 0 for record in case.records if record.scenario.value == "actual" and record.period <= "2026-06" and record.metric == "revenue")
    assert math.isclose(actual_h1, 11498.901, abs_tol=0.01)
    assert all(not (record.scenario.value == "actual" and record.period > "2026-06") for record in case.records)
    for scenario in ("actual", "budget", "forecast", "prior_year"):
        for record in case.records:
            if record.scenario.value != scenario or record.value is None:
                continue
            if record.metric == "revenue":
                volume = next(item.value for item in case.records if item.scenario.value == scenario and item.period == record.period and item.business_unit == record.business_unit and item.metric == "volume")
                ticket = next(item.value for item in case.records if item.scenario.value == scenario and item.period == record.period and item.business_unit == record.business_unit and item.metric == "average_ticket")
                assert math.isclose(record.value, volume * ticket, abs_tol=0.01)


def test_profit_allocation_indices_create_distinct_margins_and_group_anchors():
    rows = build_rows()

    def total(scenario, periods, metric):
        return sum(float(row["value"]) for row in rows if row["scenario"] == scenario and row["period"] in periods and row["metric"] == metric)

    h1 = {f"2026-{month:02d}" for month in range(1, 7)}
    fy = {f"2026-{month:02d}" for month in range(1, 13)}
    assert math.isclose(total("actual", h1, "revenue"), 11498.901, abs_tol=0.01)
    assert math.isclose(total("actual", h1, "gross_profit"), 5093.676, abs_tol=0.01)
    assert math.isclose(total("actual", h1, "operating_profit"), 1639.91, abs_tol=0.01)
    assert math.isclose(total("prior_year", h1, "revenue"), 9393.112, abs_tol=0.01)
    assert math.isclose(total("prior_year", h1, "gross_profit"), 4156.918, abs_tol=0.01)
    assert math.isclose(total("prior_year", h1, "operating_profit"), 1545.949, abs_tol=0.01)
    assert math.isclose(total("prior_year", fy, "revenue"), 21443.827, abs_tol=0.01)
    assert math.isclose(total("prior_year", fy, "gross_profit"), 9648.1, abs_tol=0.01)
    assert math.isclose(total("prior_year", fy, "operating_profit"), 3303.123, abs_tol=0.01)

    by_unit = defaultdict(lambda: defaultdict(float))
    for row in rows:
        if row["scenario"] == "actual" and row["period"] in h1 and row["metric"] in {"revenue", "gross_profit", "operating_profit"}:
            by_unit[row["business_unit"]][row["metric"]] += float(row["value"])
    gross_margins = {round(values["gross_profit"] / values["revenue"], 6) for values in by_unit.values()}
    operating_margins = {round(values["operating_profit"] / values["revenue"], 6) for values in by_unit.values()}
    assert len(gross_margins) == 3
    assert len(operating_margins) == 3


def test_profit_driver_bridge_reconciles_each_business_unit(case):
    from src.services.planning_service import build_dashboard

    dashboard = build_dashboard(case, "all", "all")
    for row in dashboard.business_unit_variances:
        actual = {"revenue": row.revenue_actual, "gross_profit": row.gross_profit_actual, "operating_expense": row.operating_expense_actual}
        budget = {"revenue": row.revenue_budget, "gross_profit": row.gross_profit_budget, "operating_expense": row.operating_expense_budget}
        effects = calculate_profit_effects(actual, budget, {"price": row.price_amount or 0, "volume": row.volume_amount or 0, "mix": row.mix_amount or 0})
        assert math.isclose(sum(effects.values()), row.operating_profit_variance or 0, abs_tol=0.01)
        assert row.profit_driver in effects


def test_pvm_bridge_reconciles_to_revenue_variance(case):
    bridge, _ = calculate_pvm(tuple(case.records), {"MINISO - Chinese Mainland", "MINISO - Overseas", "TOP TOY - Global"}, {f"2026-{month:02d}" for month in range(1, 7)})
    assert abs(bridge.reconciliation_difference or 1) <= 0.01
    assert math.isclose((bridge.actual_revenue or 0) - (bridge.budget_revenue or 0), (bridge.volume or 0) + (bridge.mix or 0) + (bridge.price or 0), abs_tol=0.01)


def test_favorability_and_safe_denominators():
    assert status_for("revenue", 20, 100) == "Favorable"
    assert status_for("operating_expense", 20, 100) == "Unfavorable"
    assert status_for("revenue", 0.5, 100) == "Neutral"
    assert safe_pct(1, 0) is None
    assert safe_pct(None, 1) is None
