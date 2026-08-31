"""Dashboard aggregation service."""

from __future__ import annotations

from src.models.planning import DataSource, KpiSnapshot, MonthlyTrendPoint, PlanningDashboardResponse
from src.repositories.case_repository import CaseData
from src.services.case_builder import validate_case_records
from src.services.insight_service import make_insights
from src.services.pvm_service import calculate_pvm
from src.services.variance_service import aggregate_total, make_variance_rows, safe_pct, status_for


MONTHS = [f"2026-{month:02d}" for month in range(1, 13)]
YTD_MONTHS = set(MONTHS[:6])
FY_MONTHS = set(MONTHS)
METRIC_LABELS = {
    "revenue": ("Revenue", "RMB millions"),
    "gross_profit": ("Gross Profit", "RMB millions"),
    "operating_profit": ("Operating Profit", "RMB millions"),
    "operating_margin": ("Operating Margin", "percent"),
}


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


def _kpis(case: CaseData, units: set[str]) -> list[KpiSnapshot]:
    result = []
    for metric, (label, unit) in METRIC_LABELS.items():
        actual = _metric_total(case, "actual", YTD_MONTHS, metric, units)
        budget = _metric_total(case, "budget", YTD_MONTHS, metric, units)
        prior = _metric_total(case, "prior_year", YTD_MONTHS, metric, units)
        fy_budget = _metric_total(case, "budget", FY_MONTHS, metric, units)
        fy_forecast = _metric_total(case, "forecast", FY_MONTHS, metric, units)
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


def _trend(case: CaseData, units: set[str]) -> list[MonthlyTrendPoint]:
    return [MonthlyTrendPoint(
        period=month,
        actual=_metric_total(case, "actual", {month}, "revenue", units),
        budget=_metric_total(case, "budget", {month}, "revenue", units),
        forecast=_metric_total(case, "forecast", {month}, "revenue", units),
        prior_year=_metric_total(case, "prior_year", {month}, "revenue", units),
    ) for month in MONTHS]


def build_dashboard(case: CaseData, brand: str, market: str) -> PlanningDashboardResponse:
    validate_case_records(case.records)
    combinations = valid_combinations(case)
    units = selected_units(case, brand, market)
    pvm, pvm_by_unit = calculate_pvm(case.records, units, YTD_MONTHS)
    if pvm.reconciliation_difference is not None and abs(pvm.reconciliation_difference) > 0.01:
        raise ValueError("PVM reconciliation failed")
    rows = make_variance_rows(case.records, units, YTD_MONTHS, FY_MONTHS, pvm_by_unit)
    sources = [DataSource(**source) for source in case.metadata["data_sources"]]
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
        kpis=_kpis(case, units),
        monthly_trend=_trend(case, units),
        business_unit_variances=rows,
        pvm_bridge=pvm,
        management_insights=make_insights(rows),
        data_sources=sources,
        provenance_legend=case.metadata["provenance_legend"],
    )
