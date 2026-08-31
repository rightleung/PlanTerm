import math

from scripts.build_miniso_case import build_rows
from src.models.planning import PlanningRecord
from src.services.case_builder import validate_case_records
from src.services.pvm_service import calculate_pvm
from src.services.variance_service import safe_pct, status_for


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
