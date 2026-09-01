"""Dashboard aggregation service."""

from __future__ import annotations

from src.models.planning import DataSource, KpiSnapshot, MonthlyTrendPoint, PlanningDashboardResponse
from src.repositories.case_repository import CaseData
from src.services.case_builder import validate_case_records
from src.services.insight_service import make_insights
from src.services.pvm_service import calculate_pvm
from src.services.variance_service import aggregate_total, make_variance_rows, safe_pct, status_for
from src.services.scenario_service import seed_rows, preview as scenario_preview


MONTHS = [f"2026-{month:02d}" for month in range(1, 13)]
YTD_MONTHS = set(MONTHS[:6])
FY_MONTHS = set(MONTHS)
METRIC_LABELS = {
    "revenue": ("Revenue", "RMB millions"),
    "gross_profit": ("Gross Profit", "RMB millions"),
    "operating_profit": ("Operating Profit", "RMB millions"),
    "operating_margin": ("Operating Margin", "percent"),
}
SCENARIO_METRICS = ("revenue", "gross_profit", "operating_profit")


def _scenario_rollups(category_detail: list[dict], plan_variant: str, units: set[str]) -> tuple[dict, dict]:
    """Project validated category rows into selected-variant dashboard totals."""
    h2: dict[tuple[str, str, str], float] = {}
    fy: dict[tuple[str, str], float] = {}
    for item in category_detail:
        if item.get("plan_variant") != plan_variant or item.get("business_unit") not in units:
            continue
        unit = item["business_unit"]
        period = item.get("period")
        if period in MONTHS[6:]:
            for metric in SCENARIO_METRICS:
                key = (period, unit, metric)
                h2[key] = h2.get(key, 0.0) + float(item.get(metric) or 0.0)
        elif period == "FY2026":
            for metric in SCENARIO_METRICS:
                key = (unit, metric)
                fy[key] = fy.get(key, 0.0) + float(item.get(metric) or 0.0)
    return h2, fy


def valid_combinations(case: CaseData) -> list[dict[str, str]]:
    """Derive filter combinations from the case records, not UI mappings."""
    combinations = {
        (record.brand, record.market, record.business_unit)
        for record in case.records
    }
    return [
        {"brand": brand, "market": market, "business_unit": business_unit}
        for brand, market, business_unit in sorted(combinations)
    ]


def filters_are_compatible(case: CaseData, brand: str, market: str) -> bool:
    combinations = valid_combinations(case)
    return any(
        (brand == "all" or combination["brand"] == brand)
        and (market == "all" or combination["market"] == market)
        for combination in combinations
    )


def selected_units(case: CaseData, brand: str, market: str) -> set[str]:
    return {
        combination["business_unit"]
        for combination in valid_combinations(case)
        if (brand == "all" or combination["brand"] == brand)
        and (market == "all" or combination["market"] == market)
    }


def _metric_total(case: CaseData, scenario: str, periods: set[str], metric: str, units: set[str]) -> float | None:
    if metric == "operating_margin":
        revenue = _metric_total(case, scenario, periods, "revenue", units)
        operating_profit = _metric_total(case, scenario, periods, "operating_profit", units)
        return safe_pct(operating_profit, revenue)
    return aggregate_total(case.records, scenario, periods, metric, units)


def _kpis(case: CaseData, units: set[str], scenario_fy: dict[tuple[str, str], float]) -> list[KpiSnapshot]:
    result = []
    for metric, (label, unit) in METRIC_LABELS.items():
        actual = _metric_total(case, "actual", YTD_MONTHS, metric, units)
        budget = _metric_total(case, "budget", YTD_MONTHS, metric, units)
        prior = _metric_total(case, "prior_year", YTD_MONTHS, metric, units)
        fy_budget = _metric_total(case, "budget", FY_MONTHS, metric, units)
        if metric == "operating_margin":
            selected_revenue = sum(scenario_fy.get((unit, "revenue"), 0.0) for unit in units)
            selected_operating_profit = sum(scenario_fy.get((unit, "operating_profit"), 0.0) for unit in units)
            fy_forecast = safe_pct(selected_operating_profit, selected_revenue)
        else:
            fy_forecast = sum((scenario_fy.get((unit, metric), 0.0) for unit in units), 0.0) or None
        variance = None if actual is None or budget is None else actual - budget
        yoy = None if actual is None or prior in (None, 0) else (actual - prior) / abs(prior)
        result.append(KpiSnapshot(
            metric=metric,
            label=label,
            unit=unit,
            actual_ytd=actual,
            budget_ytd=budget,
            variance_amount=variance,
            variance_pct=safe_pct(variance, budget),
            prior_year_ytd=prior,
            yoy_pct=yoy,
            fy_budget=fy_budget,
            fy_forecast=fy_forecast,
            forecast_gap=None if fy_forecast is None or fy_budget is None else fy_forecast - fy_budget,
            status=status_for(metric, variance, budget),
        ))
    return result


def _trend(case: CaseData, units: set[str], scenario_h2: dict[tuple[str, str, str], float]) -> list[MonthlyTrendPoint]:
    return [MonthlyTrendPoint(
        period=month,
        actual=_metric_total(case, "actual", {month}, "revenue", units),
        budget=_metric_total(case, "budget", {month}, "revenue", units),
        forecast=(
            _metric_total(case, "actual", {month}, "revenue", units)
            if month in MONTHS[:6]
            else (sum((scenario_h2.get((month, unit, "revenue"), 0.0) for unit in units), 0.0) or None)
        ),
        prior_year=_metric_total(case, "prior_year", {month}, "revenue", units),
    ) for month in MONTHS]


def build_dashboard(case: CaseData, brand: str, market: str, plan_variant: str = "base", planning_input_source: str = "seed", planning_rows=None) -> PlanningDashboardResponse:
    validate_case_records(case.records)
    combinations = valid_combinations(case)
    units = selected_units(case, brand, market)
    pvm, pvm_by_unit = calculate_pvm(case.records, units, YTD_MONTHS)
    if pvm.reconciliation_difference is not None and abs(pvm.reconciliation_difference) > 0.01:
        raise ValueError("PVM reconciliation failed")
    rows = make_variance_rows(case.records, units, YTD_MONTHS, FY_MONTHS, pvm_by_unit)
    sources = [DataSource(**source) for source in case.metadata["data_sources"]]
    category_detail, comparison, category_context = scenario_preview(case, planning_rows, plan_variant) if planning_rows is not None else scenario_preview(case, [r.model_dump() for r in seed_rows(case)], plan_variant)
    # Scenario detail follows the same brand/market filter as the dashboard;
    # the underlying matrix is still validated in full before this projection.
    category_detail = [item for item in category_detail if item.get("business_unit") in units]
    category_context = [item for item in category_context if item.get("business_unit") in units]
    scenario_h2, scenario_fy = _scenario_rollups(category_detail, plan_variant, units)
    # Keep committed Actual/Budget/Prior/PVM fields unchanged; replace only
    # Forecast-facing BU values with the selected scenario projection.
    for row in rows:
        fy_forecast = scenario_fy.get((row.business_unit, "revenue"))
        row.fy_forecast = fy_forecast
        row.forecast_gap = None if fy_forecast is None or row.fy_budget is None else fy_forecast - row.fy_budget
    comparison = {"selected_plan_variant": plan_variant}
    for metric in ("revenue", "gross_profit", "operating_profit"):
        base_value = sum(item.get(metric, 0) for item in category_detail if item.get("period") == "FY2026" and item.get("plan_variant") == "base")
        selected_value = sum(item.get(metric, 0) for item in category_detail if item.get("period") == "FY2026" and item.get("plan_variant") == plan_variant)
        comparison[metric] = {"base_fy_forecast": base_value, "selected_fy_forecast": selected_value, "delta": selected_value - base_value, "unit": "RMB millions"}
    return PlanningDashboardResponse(
        metadata=case.metadata,
        assumptions=case.assumptions,
        available_filters={
            "brands": ["all", *sorted({combination["brand"] for combination in combinations})],
            "markets": ["all", *sorted({combination["market"] for combination in combinations})],
            "business_units": sorted({combination["business_unit"] for combination in combinations}),
            "valid_combinations": combinations,
        },
        selected_filters={"brand": brand, "market": market},
        kpis=_kpis(case, units, scenario_fy),
        monthly_trend=_trend(case, units, scenario_h2),
        business_unit_variances=rows,
        pvm_bridge=pvm,
        management_insights=make_insights(rows),
        data_sources=sources,
        provenance_legend=case.metadata["provenance_legend"],
        selected_plan_variant=plan_variant,
        planning_input_source=planning_input_source,
        planning_horizon={"locked_through":"2026-06", "editable_from":"2026-07", "editable_to":"2026-12"},
        category_detail=category_detail,
        category_detail_context=category_context,
        scenario_comparison=comparison,
        category_taxonomy_disclosure=case.taxonomy or {},
    )
