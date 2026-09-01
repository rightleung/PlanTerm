"""Dashboard aggregation service."""

from __future__ import annotations

from decimal import Decimal

from src.models.planning import DataSource, KpiSnapshot, MonthlyTrendPoint, PlanningDashboardResponse
from src.repositories.case_repository import CaseData
from src.services.case_builder import validate_case_records
from src.services.insight_service import make_insights
from src.services.pvm_service import calculate_pvm
from src.services.variance_service import aggregate_total, calculate_profit_bridge, make_variance_rows, safe_pct, status_for
from src.services.scenario_service import seed_rows, preview as scenario_preview
from src.services.csv_input_service import InputError, parse_json_rows
from src.services.category_plan_service import calculate_rows, is_committed_variant_seed
from src.services.working_capital_service import calculate_working_capital, dec, json_float
from src.services.cash_forecast_service import calculate_cash_bridge
from src.services.forecast_accuracy_service import calculate_forecast_accuracy
from src.services.action_service import build_actions
from src.services.headcount_service import build_headcount
from src.services.assumption_registry import build_assumption_registry
from src.services.decision_log_service import DecisionLogService, seeded_decision_rows


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
    h2: dict[tuple[str, str, str], Decimal] = {}
    fy: dict[tuple[str, str], Decimal] = {}
    for item in category_detail:
        if item.get("plan_variant") != plan_variant or item.get("business_unit") not in units:
            continue
        unit = item["business_unit"]
        period = item.get("period")
        if period in MONTHS[6:]:
            for metric in SCENARIO_METRICS:
                key = (period, unit, metric)
                h2[key] = h2.get(key, Decimal(0)) + (dec(item.get(metric), nullable=False) or Decimal(0))
        elif period == "FY2026":
            for metric in SCENARIO_METRICS:
                key = (unit, metric)
                fy[key] = fy.get(key, Decimal(0)) + (dec(item.get(metric), nullable=False) or Decimal(0))
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


def _metric_total(case: CaseData, scenario: str, periods: set[str], metric: str, units: set[str]) -> Decimal | None:
    if metric == "operating_margin":
        revenue = _metric_total(case, scenario, periods, "revenue", units)
        operating_profit = _metric_total(case, scenario, periods, "operating_profit", units)
        return safe_pct(operating_profit, revenue)
    return aggregate_total(case.records, scenario, periods, metric, units)


def _kpis(case: CaseData, units: set[str], scenario_fy: dict[tuple[str, str], Decimal]) -> list[KpiSnapshot]:
    result = []
    for metric, (label, unit) in METRIC_LABELS.items():
        actual = _metric_total(case, "actual", YTD_MONTHS, metric, units)
        budget = _metric_total(case, "budget", YTD_MONTHS, metric, units)
        prior = _metric_total(case, "prior_year", YTD_MONTHS, metric, units)
        fy_budget = _metric_total(case, "budget", FY_MONTHS, metric, units)
        if metric == "operating_margin":
            selected_revenue = sum((scenario_fy.get((unit, "revenue"), Decimal(0)) for unit in units), Decimal(0))
            selected_operating_profit = sum((scenario_fy.get((unit, "operating_profit"), Decimal(0)) for unit in units), Decimal(0))
            fy_forecast = safe_pct(selected_operating_profit, selected_revenue)
        else:
            fy_forecast = sum((scenario_fy.get((unit, metric), Decimal(0)) for unit in units), Decimal(0)) or None
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


def _trend(case: CaseData, units: set[str], scenario_h2: dict[tuple[str, str, str], Decimal]) -> list[MonthlyTrendPoint]:
    return [MonthlyTrendPoint(
        period=month,
        actual=_metric_total(case, "actual", {month}, "revenue", units),
        budget=_metric_total(case, "budget", {month}, "revenue", units),
        forecast=(
            _metric_total(case, "actual", {month}, "revenue", units)
            if month in MONTHS[:6]
            else (sum((scenario_h2.get((month, unit, "revenue"), Decimal(0)) for unit in units), Decimal(0)) or None)
        ),
        prior_year=_metric_total(case, "prior_year", {month}, "revenue", units),
    ) for month in MONTHS]


def build_dashboard(case: CaseData, brand: str, market: str, plan_variant: str = "base", planning_input_source: str = "seed", planning_rows=None) -> PlanningDashboardResponse:
    validate_case_records(case.records)
    governance_metadata = build_assumption_registry(case)
    combinations = valid_combinations(case)
    units = selected_units(case, brand, market)
    pvm, pvm_by_unit = calculate_pvm(case.records, units, YTD_MONTHS)
    if pvm.reconciliation_difference is not None and abs(pvm.reconciliation_difference) > 0.01:
        raise ValueError("PVM reconciliation failed")
    rows = make_variance_rows(case.records, units, YTD_MONTHS, FY_MONTHS, pvm_by_unit)
    actual_profit_bridge_inputs = {
        metric: _metric_total(case, "actual", YTD_MONTHS, metric, units)
        for metric in ("revenue", "gross_profit", "operating_profit", "operating_expense")
    }
    budget_profit_bridge_inputs = {
        metric: _metric_total(case, "budget", YTD_MONTHS, metric, units)
        for metric in ("revenue", "gross_profit", "operating_profit", "operating_expense")
    }
    profit_bridge = calculate_profit_bridge(actual_profit_bridge_inputs, budget_profit_bridge_inputs, pvm)
    if profit_bridge.reconciliation_difference is not None and abs(profit_bridge.reconciliation_difference) > 0.01:
        raise ValueError("Profit bridge reconciliation failed")
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
        row.fy_forecast = None if fy_forecast is None else float(fy_forecast)
        row.forecast_gap = None if fy_forecast is None or row.fy_budget is None else float(fy_forecast - Decimal(str(row.fy_budget)))
    committed_category_detail, _, _ = scenario_preview(case, [r.model_dump() for r in seed_rows(case)], "base")
    committed_category_detail = [item for item in committed_category_detail if item.get("business_unit") in units]
    comparison = {"selected_plan_variant": plan_variant}
    for metric in ("revenue", "gross_profit", "operating_profit"):
        # Always compare to the committed Base seed. This keeps a valid edit
        # to the Base plan visible as a delta instead of comparing it with
        # itself, while the selected scenario remains fully recalculated.
        base_value = sum((dec(item.get(metric), nullable=False) or Decimal(0) for item in committed_category_detail if item.get("period") == "FY2026" and item.get("plan_variant") == "base"), Decimal(0))
        selected_value = sum((dec(item.get(metric), nullable=False) or Decimal(0) for item in category_detail if item.get("period") == "FY2026" and item.get("plan_variant") == plan_variant), Decimal(0))
        comparison[metric] = {"base_fy_forecast": float(base_value), "selected_fy_forecast": float(selected_value), "delta": float(selected_value - base_value), "unit": "RMB millions"}
    return PlanningDashboardResponse(
        metadata={**case.metadata, "assumption_version": governance_metadata["assumption_version"], "git_sha": governance_metadata["git_sha"]},
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
        profit_bridge=profit_bridge,
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


def build_operating_decision(case: CaseData, plan_variant: str = "base", planning_input_source: str = "seed", planning_rows=None, working_capital_rows=None, cash_assumption_rows=None, actions=None, headcount_rows=None) -> dict:
    """Compose the additive v0.3 operating-decision fields."""
    return build_operating_plan(case, plan_variant, planning_input_source, planning_rows, working_capital_rows, cash_assumption_rows, actions, headcount_rows)


OD_MONTHS = [f"2026-{month:02d}" for month in range(7, 13)]
UNITS = ("MINISO - Chinese Mainland", "MINISO - Overseas", "TOP TOY - Global")
VARIANTS = ("base", "upside", "downside")


def _validated_decimal(value, *, row: int, field: str):
    try:
        return dec(value)
    except ValueError as exc:
        raise InputError("invalid_range", "Invalid finite numeric assumption", {"row": row, "field": field}) from exc


def _records(case, scenario, period, unit, metric):
    return sum((dec(r.value) or Decimal(0) for r in case.records if r.scenario.value == scenario and r.period == period and r.business_unit == unit and r.metric == metric), Decimal(0))


def _validate_wc_rows(case, rows, selected_variant="base"):
    if not isinstance(rows, list):
        raise InputError("incomplete_input_matrix", "Complete working-capital rows are required")
    expected = {(selected_variant, period, unit) for period in OD_MONTHS for unit in UNITS}
    seen = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise InputError("invalid_input_row", "Working-capital row must be an object", {"row": index})
        required = {"case_id", "plan_variant", "period", "business_unit", "ar_days", "inventory_days", "ap_days", "provenance"}
        missing = required - set(row)
        unknown = set(row) - required
        if missing:
            raise InputError("validation_error", "Working-capital row is missing required fields", {"row": index, "missing": sorted(missing)})
        if unknown:
            raise InputError("unexpected_input_key", "Working-capital row has unexpected fields", {"row": index, "fields": sorted(unknown)})
        if any(not isinstance(row[field], str) for field in ("case_id", "plan_variant", "period", "business_unit")):
            raise InputError("validation_error", "Working-capital identity fields must be strings", {"row": index})
        key = (row["plan_variant"], row["period"], row["business_unit"])
        if key in seen:
            raise InputError("duplicate_input_key", "Duplicate working-capital row", {"row": index})
        seen.add(key)
        if key not in expected:
            raise InputError("unexpected_input_key", "Unknown working-capital row key", {"row": index})
        if row["case_id"] != case.case_id:
            raise InputError("invalid_input_row", "Unknown case in working-capital row", {"row": index})
        if row["provenance"] != "synthetic_plan":
            raise InputError("invalid_provenance", "Working-capital assumptions must be synthetic_plan", {"row": index})
        for field in ("ar_days", "inventory_days", "ap_days"):
            value = _validated_decimal(row.get(field), row=index, field=field)
            if value is not None and (value < 0 or value > 3650):
                raise InputError("invalid_range", "Invalid working-capital day assumption", {"row": index, "field": field})
    if seen != expected:
        raise InputError("incomplete_input_matrix", "Complete working-capital rows are required", {"missing_count": len(expected - seen)})


def _validate_cash_rows(case, rows, selected_variant="base"):
    if not isinstance(rows, list):
        raise InputError("incomplete_input_matrix", "Complete cash-assumption rows are required")
    expected = {(selected_variant, period) for period in OD_MONTHS}
    seen = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise InputError("validation_error", "Cash-assumption row must be an object", {"row": index})
        required = {"case_id", "plan_variant", "period", "opening_cash", "minimum_cash_buffer", "capex", "other_cash_items", "provenance"}
        missing, unknown = required - set(row), set(row) - required
        if missing:
            raise InputError("validation_error", "Cash-assumption row is missing required fields", {"row": index, "missing": sorted(missing)})
        if unknown:
            raise InputError("unexpected_input_key", "Cash-assumption row has unexpected fields", {"row": index, "fields": sorted(unknown)})
        if any(not isinstance(row[field], str) for field in ("case_id", "plan_variant", "period")):
            raise InputError("validation_error", "Cash-assumption identity fields must be strings", {"row": index})
        key = (row["plan_variant"], row["period"])
        if key in seen:
            raise InputError("duplicate_input_key", "Duplicate cash-assumption row", {"row": index})
        seen.add(key)
        if key not in expected:
            raise InputError("unexpected_input_key", "Unknown cash-assumption row key", {"row": index})
        if row["case_id"] != case.case_id:
            raise InputError("invalid_input_row", "Unknown case in cash-assumption row", {"row": index})
        if row["provenance"] != "synthetic_plan":
            raise InputError("invalid_provenance", "Cash assumptions must be synthetic_plan", {"row": index})
        for field in ("opening_cash", "minimum_cash_buffer", "capex", "other_cash_items"):
            value = _validated_decimal(row.get(field), row=index, field=field)
            if value is not None and abs(value) > Decimal("1000000"):
                raise InputError("invalid_range", "Invalid cash assumption", {"row": index, "field": field})
    if seen != expected:
        raise InputError("incomplete_input_matrix", "Complete cash-assumption rows are required", {"missing_count": len(expected - seen)})


def _seed_wc(case):
    return [dict(row) for row in case.working_capital_seed]


def _seed_cash(case):
    return [dict(row, opening_cash=case.cash_assumptions.get("opening_cash"), minimum_cash_buffer=case.cash_assumptions.get("minimum_cash_buffer")) for row in case.cash_assumptions.get("rows", [])]


def _metric_detail(details, variant, period, unit, metric):
    return sum((dec(item.get(metric)) or Decimal(0) for item in details if item.get("plan_variant") == variant and item.get("period") == period and item.get("business_unit") == unit), Decimal(0))


def _portfolio_ccc(rows: list[dict]) -> Decimal | None:
    """Calculate a portfolio CCC with revenue/COGS-weighted day assumptions."""
    eligible = [row for row in rows if row.get("status") == "eligible"]
    revenue = sum((dec(row.get("revenue"), nullable=False) or Decimal(0) for row in eligible), Decimal(0))
    cogs = sum((dec(row.get("cogs"), nullable=False) or Decimal(0) for row in eligible), Decimal(0))
    if not eligible or revenue == 0 or cogs == 0:
        return None
    ar_days = sum((dec(row.get("revenue"), nullable=False) or Decimal(0)) * (dec(row.get("ar_days"), nullable=False) or Decimal(0)) for row in eligible) / revenue
    inventory_days = sum((dec(row.get("cogs"), nullable=False) or Decimal(0)) * (dec(row.get("inventory_days"), nullable=False) or Decimal(0)) for row in eligible) / cogs
    ap_days = sum((dec(row.get("cogs"), nullable=False) or Decimal(0)) * (dec(row.get("ap_days"), nullable=False) or Decimal(0)) for row in eligible) / cogs
    return ar_days + inventory_days - ap_days


def build_operating_plan(case, plan_variant="base", planning_input_source="seed", planning_rows=None, working_capital_rows=None, cash_assumption_rows=None, actions=None, headcount_rows=None):
    if plan_variant not in VARIANTS:
        raise InputError("invalid_variant", "Unknown plan variant")
    rows = seed_rows(case) if planning_rows is None else parse_json_rows(planning_rows, case.case_id, case.taxonomy)
    details, comparison, _ = calculate_rows(case, rows, plan_variant)
    wc_rows = _seed_wc(case) if working_capital_rows is None else working_capital_rows
    cash_rows = _seed_cash(case) if cash_assumption_rows is None else cash_assumption_rows
    # Client previews are scoped to the selected variant; committed seeds contain all three.
    if working_capital_rows is not None:
        _validate_wc_rows(case, wc_rows, plan_variant)
    if cash_assumption_rows is not None:
        _validate_cash_rows(case, cash_rows, plan_variant)
    wc_by_variant = {variant: [dict(row) for row in _seed_wc(case) if row.get("plan_variant") == variant] for variant in VARIANTS}
    cash_by_variant = {variant: [dict(row) for row in _seed_cash(case) if row.get("plan_variant") == variant] for variant in VARIANTS}
    if working_capital_rows is not None:
        wc_by_variant[plan_variant] = wc_rows
    if cash_assumption_rows is not None:
        cash_by_variant[plan_variant] = cash_rows
    for variant in VARIANTS:
        _validate_wc_rows(case, wc_by_variant[variant], variant)
        _validate_cash_rows(case, cash_by_variant[variant], variant)

    def calculate_variant(variant):
        wc_lookup = {(r["plan_variant"], r["period"], r["business_unit"]): r for r in wc_by_variant[variant]}
        cash_lookup = {(r["plan_variant"], r["period"]): r for r in cash_by_variant[variant]}
        working_capital, cash_bridge = [], []
        for period in OD_MONTHS:
            for unit in UNITS:
                assumption = wc_lookup[(variant, period, unit)]
                revenue = _metric_detail(details, variant, period, unit, "revenue")
                cogs = _metric_detail(details, variant, period, unit, "cost_of_sales")
                prior_revenue = _records(case, "actual", "2026-06", unit, "revenue")
                prior_cogs = _records(case, "actual", "2026-06", unit, "cost_of_sales")
                current = calculate_working_capital({**assumption, "revenue": revenue, "cogs": cogs})
                prior = calculate_working_capital({**assumption, "revenue": prior_revenue, "cogs": prior_cogs})
                current["business_unit"], current["period"], current["plan_variant"] = unit, period, variant
                current["prior_ar_balance"] = prior["ar_balance"]
                current["prior_inventory_balance"] = prior["inventory_balance"]
                current["prior_ap_balance"] = prior["ap_balance"]
                working_capital.append(current)
            cash = cash_lookup[(variant, period)]
            op = sum((_metric_detail(details, variant, period, unit, "operating_profit") for unit in UNITS), Decimal(0))
            current_wc = [row for row in working_capital if row["period"] == period]
            previous_wc = [row for row in working_capital if row["period"] == OD_MONTHS[OD_MONTHS.index(period)-1]] if period != OD_MONTHS[0] else []
            if previous_wc:
                prior_ar = sum((dec(row.get("ar_balance"), nullable=False) for row in previous_wc), Decimal(0))
                prior_inventory = sum((dec(row.get("inventory_balance"), nullable=False) for row in previous_wc), Decimal(0))
                prior_ap = sum((dec(row.get("ap_balance"), nullable=False) for row in previous_wc), Decimal(0))
            else:
                prior_ar = sum((dec(row.get("prior_ar_balance"), nullable=False) for row in current_wc), Decimal(0))
                prior_inventory = sum((dec(row.get("prior_inventory_balance"), nullable=False) for row in current_wc), Decimal(0))
                prior_ap = sum((dec(row.get("prior_ap_balance"), nullable=False) for row in current_wc), Decimal(0))
            bridge = {**cash, "period": period, "plan_variant": variant, "operating_profit": op, "prior_ar": prior_ar, "current_ar": sum((dec(row.get("ar_balance"), nullable=False) for row in current_wc), Decimal(0)), "prior_inventory": prior_inventory, "current_inventory": sum((dec(row.get("inventory_balance"), nullable=False) for row in current_wc), Decimal(0)), "current_ap": sum((dec(row.get("ap_balance"), nullable=False) for row in current_wc), Decimal(0)), "prior_ap": prior_ap}
            cash_bridge.append(calculate_cash_bridge(bridge))
        return working_capital, cash_bridge

    variant_results = {variant: calculate_variant(variant) for variant in VARIANTS}
    working_capital, cash_bridge = variant_results[plan_variant]
    accuracy = calculate_forecast_accuracy(case.forecast_snapshots)
    actions_out = build_actions(case_id=case.case_id, cash_bridge=cash_bridge[-1] if cash_bridge else None, forecast_accuracy=accuracy, actions=actions)
    closing_values = [row.get("closing_illustrative_cash") for row in cash_bridge if row.get("closing_illustrative_cash") is not None]
    headrooms = [row.get("headroom") for row in cash_bridge if row.get("headroom") is not None]
    decision_table = []
    committed_details, _, _ = calculate_rows(case, seed_rows(case), "base")
    base_fy_revenue = sum((_metric_detail(committed_details, "base", "FY2026", unit, "revenue") for unit in UNITS), Decimal(0))
    base_fy_op = sum((_metric_detail(committed_details, "base", "FY2026", unit, "operating_profit") for unit in UNITS), Decimal(0))
    for variant in VARIANTS:
        variant_wc, variant_cash = variant_results[variant]
        fy_revenue = sum((_metric_detail(details, variant, "FY2026", unit, "revenue") for unit in UNITS), Decimal(0))
        fy_op = sum((_metric_detail(details, variant, "FY2026", unit, "operating_profit") for unit in UNITS), Decimal(0))
        valid_cash = [row for row in variant_cash if row.get("closing_illustrative_cash") is not None]
        minimum_cash = min(valid_cash, key=lambda row: row.get("headroom")) if valid_cash else None
        variant_ccc = None
        if minimum_cash:
            variant_ccc = json_float(_portfolio_ccc([row for row in variant_wc if row.get("period") == minimum_cash.get("period")]))
        decision_table.append({"plan_variant": variant, "fy_revenue_delta": float(fy_revenue - base_fy_revenue), "fy_operating_profit_delta": float(fy_op - base_fy_op), "minimum_cash_month": minimum_cash.get("period") if minimum_cash else None, "cash_headroom": minimum_cash.get("headroom") if minimum_cash else None, "ccc": variant_ccc, "top_revenue_driver": "H2 category drivers", "top_profit_driver": "Operating profit", "top_cash_driver": "Working capital", "owner": "Group FP&A", "next_review_date": "2026-07-31", "provenance": "calculated"})
    # Residual evidence is surfaced rather than asserted by flag.
    base_committed = is_committed_variant_seed(case, rows, "base")
    base_h2_residual = sum((_metric_detail(details, "base", period, unit, "revenue") - _records(case, "forecast", period, unit, "revenue") for period in OD_MONTHS for unit in UNITS), Decimal(0)) if base_committed else Decimal(0)
    cash_residuals = [dec(row.get("cash_identity_residual"), nullable=False) for row in cash_bridge if row.get("cash_identity_residual") is not None]
    max_cash_residual = max((abs(x) for x in cash_residuals), default=None)
    category_ok = abs(base_h2_residual) <= Decimal("0.01")
    cash_ok = max_cash_residual is not None and max_cash_residual <= Decimal("0.01")
    headcount = build_headcount(case, plan_variant, headcount_rows)
    reconciliation = {"status": "reconciled" if category_ok and cash_ok and headcount["reconciliation_evidence"]["status"] == "reconciled" else "not_reconciled", "tolerance_rmb_millions": 0.01, "cash_bridge": {"status": "reconciled" if cash_ok else "not_reconciled", "max_residual": json_float(max_cash_residual)}, "category_rollup": {"status": "reconciled" if category_ok else "not_reconciled", "revenue_residual": json_float(base_h2_residual), "anchor": "committed_forecast" if base_committed else "scenario_internal"}, "headcount": headcount["reconciliation_evidence"]}
    # Governance is additive and derived only from the deterministic operating-plan result.
    decision_log = DecisionLogService(session_id=f"{case.case_id}:{plan_variant}:demo")
    assumption_registry = build_assumption_registry(case)
    seeded_decisions = seeded_decision_rows(case.case_id, case.metadata["as_of_date"], decision_table)
    for table_row, row in zip(decision_table, seeded_decisions):
        table_row["evidence"] = row["evidence"]
    for row in seeded_decisions:
        decision_log.append(row)
    return {"as_of_date": case.metadata["as_of_date"], "planning_horizon": {"locked_through": "2026-06", "editable_from": "2026-07", "editable_to": "2026-12"}, "plan_variant": plan_variant, "provenance_legend": case.metadata["provenance_legend"], "working_capital": {"rows": working_capital, "unit": "RMB millions", "input_provenance": "synthetic_plan", "disclosure": "Synthetic planning assumption; not a bank-reported working capital."}, "cash_bridge": {"rows": cash_bridge, "closing_illustrative_cash": closing_values[-1] if closing_values else None, "input_provenance": "synthetic_plan", "disclosure": "Illustrative cash balance; not a bank-reported cash balance."}, "forecast_accuracy": accuracy, "actions": actions_out, "decision_table": decision_table, "decision_log": decision_log.export(), "assumption_registry": assumption_registry, "assumption_version": assumption_registry["assumption_version"], "git_sha": assumption_registry["git_sha"], "governance": {"scope": "session", "persistence": "none", "decision_log": decision_log.export(), "assumption_registry": assumption_registry}, "headcount_rows": headcount["headcount_rows"], "workforce_capacity": headcount, "reconciliation": reconciliation}
