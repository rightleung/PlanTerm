"""Bounded synthetic workforce-capacity calculations for the operating plan."""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, localcontext

from src.services.csv_input_service import InputError

MONTHS = tuple(f"2026-{month:02d}" for month in range(7, 13))
ROLE_GROUPS = ("store operations", "commercial", "supply chain", "finance/support")
BUSINESS_UNITS = ("MINISO - Chinese Mainland", "MINISO - Overseas", "TOP TOY - Global")
VARIANTS = ("base", "upside", "downside")
INPUT_KEYS = {"case_id", "plan_variant", "period", "business_unit", "role_group", "planned_fte", "monthly_loaded_cost", "provenance"}
TOLERANCE = Decimal("0.01")


def _dec(value, row: int | None = None, field: str = "value") -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InputError("invalid_range", "Invalid finite headcount number", {"row": row, "field": field}) from exc
    if not result.is_finite() or abs(result) > Decimal("1e9"):
        raise InputError("invalid_range", "Headcount numbers must be finite and bounded", {"row": row, "field": field})
    try:
        if not math.isfinite(float(result)):
            raise ValueError
    except (OverflowError, ValueError) as exc:
        raise InputError("invalid_range", "Headcount numbers must be finite and bounded", {"row": row, "field": field}) from exc
    return result


def _load_seed(case):
    # CaseData carries the loaded seed, keeping requests stateless and file-backed.
    return [dict(row) for row in getattr(case, "headcount_seed", ())]


def _expected(variant: str):
    return {(variant, period, unit, role) for period in MONTHS for unit in BUSINESS_UNITS for role in ROLE_GROUPS}


def validate_input_rows(case, rows, selected_variant: str) -> list[dict]:
    if not isinstance(rows, list):
        raise InputError("incomplete_input_matrix", "Complete headcount rows are required")
    expected = _expected(selected_variant)
    seen = set(); clean = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise InputError("validation_error", "Headcount row must be an object", {"row": index})
        missing = INPUT_KEYS - set(row); unknown = set(row) - INPUT_KEYS
        if missing:
            raise InputError("validation_error", "Headcount row is missing required fields", {"row": index, "missing": sorted(missing)})
        if unknown:
            raise InputError("unexpected_input_key", "Headcount row has unexpected or derived fields", {"row": index, "fields": sorted(unknown)})
        if any(not isinstance(row[field], str) for field in ("case_id", "plan_variant", "period", "business_unit", "role_group", "provenance")):
            raise InputError("validation_error", "Headcount dimensions must be strings", {"row": index})
        if row["case_id"] != case.case_id:
            raise InputError("invalid_input_row", "Unknown case in headcount row", {"row": index})
        if row["plan_variant"] != selected_variant:
            raise InputError("unexpected_input_key", "Headcount row variant does not match selection", {"row": index})
        key = (row["plan_variant"], row["period"], row["business_unit"], row["role_group"])
        if key in seen:
            raise InputError("duplicate_input_key", "Duplicate headcount row", {"row": index})
        seen.add(key)
        if key not in expected:
            raise InputError("unexpected_input_key", "Unknown headcount dimension or locked period", {"row": index})
        if row["role_group"] not in ROLE_GROUPS or row["business_unit"] not in BUSINESS_UNITS or row["period"] not in MONTHS:
            raise InputError("unexpected_input_key", "Unknown headcount dimension", {"row": index})
        if row["provenance"] != "synthetic_plan":
            raise InputError("invalid_provenance", "Headcount inputs must be synthetic_plan", {"row": index})
        planned = _dec(row["planned_fte"], index, "planned_fte")
        cost = _dec(row["monthly_loaded_cost"], index, "monthly_loaded_cost")
        if planned < 0:
            raise InputError("invalid_range", "Negative planned FTE is not permitted", {"row": index, "field": "planned_fte"})
        if cost < 0:
            raise InputError("invalid_range", "Negative loaded cost is not permitted", {"row": index, "field": "monthly_loaded_cost"})
        clean.append({**row, "planned_fte": planned, "monthly_loaded_cost": cost})
    if seen != expected:
        raise InputError("incomplete_input_matrix", "Complete headcount rows are required", {"missing_count": len(expected - seen)})
    return clean


def _revenue(case, variant: str, period: str, unit: str) -> Decimal:
    base = sum((_dec(r.value) for r in case.records if r.scenario.value == "forecast" and r.period == period and r.business_unit == unit and r.metric == "revenue"), Decimal(0))
    multiplier = _dec(case.headcount_assumptions.get("variant_revenue_multipliers", {}).get(variant, 1))
    return base * multiplier


def build_headcount(case, selected_variant: str = "base", rows=None) -> dict:
    if selected_variant not in VARIANTS:
        raise InputError("invalid_variant", "Unknown plan variant")
    source_rows = validate_input_rows(case, rows, selected_variant) if rows is not None else [dict(r) for r in _load_seed(case) if r.get("plan_variant") == selected_variant]
    if rows is None:
        source_rows = validate_input_rows(case, source_rows, selected_variant)
    assumptions = case.headcount_assumptions
    required_ratio = _dec(assumptions.get("required_fte_per_planned_fte", {}).get(selected_variant, 1))
    planned_by_bu_period = {}
    for row in source_rows:
        key = (row["period"], row["business_unit"])
        planned_by_bu_period[key] = planned_by_bu_period.get(key, Decimal(0)) + row["planned_fte"]
    output = []
    with localcontext() as context:
        context.prec = 40
        for row in source_rows:
            planned = row["planned_fte"]; cost_per = row["monthly_loaded_cost"]
            required = planned * required_ratio
            bu_revenue = _revenue(case, selected_variant, row["period"], row["business_unit"])
            bu_planned = planned_by_bu_period[(row["period"], row["business_unit"])]
            revenue = bu_revenue * planned / bu_planned if bu_planned > 0 else Decimal(0)
            loaded = planned * cost_per
            revenue_per = revenue / planned if planned > 0 else None
            gap = required - planned
            status = "zero_capacity" if planned == 0 else ("over_capacity" if gap < 0 else "capacity_gap" if gap > 0 else "balanced")
            output.append({"case_id": case.case_id, "plan_variant": selected_variant, "period": row["period"], "business_unit": row["business_unit"], "role_group": row["role_group"], "planned_fte": float(planned), "required_fte": float(required), "monthly_loaded_cost": float(cost_per), "loaded_cost": float(loaded), "revenue": float(revenue), "revenue_per_fte": float(revenue_per) if revenue_per is not None else None, "capacity_gap": float(gap), "productivity_basis": assumptions.get("productivity_basis", "Revenue / planned FTE"), "status": status, "provenance": "calculated", "input_provenance": "synthetic_plan"})
    by_role = {role: _rollup([r for r in output if r["role_group"] == role]) for role in ROLE_GROUPS}
    by_bu = {unit: _rollup([r for r in output if r["business_unit"] == unit]) for unit in BUSINESS_UNITS}
    nested = {role: {unit: _rollup([r for r in output if r["role_group"] == role and r["business_unit"] == unit]) for unit in BUSINESS_UNITS} for role in ROLE_GROUPS}
    portfolio = _rollup(output)
    locked = []
    for item in assumptions.get("locked_h1", []):
        locked.append({**item, "plan_variant": selected_variant, "provenance": "synthetic_plan", "input_provenance": "synthetic_plan"})
    base = build_headcount(case, "base", None) if selected_variant != "base" else None
    base_totals = base["rollups"]["portfolio"] if base else portfolio
    deltas = {key: float(Decimal(str(portfolio[key])) - Decimal(str(base_totals[key]))) for key in ("planned_fte", "required_fte", "loaded_cost", "capacity_gap")}
    if base:
        for role in ROLE_GROUPS:
            for key in ("planned_fte", "required_fte", "loaded_cost", "capacity_gap"):
                deltas[f"{role}.{key}"] = float(Decimal(str(by_role[role][key])) - Decimal(str(base["rollups"]["role_group"][role][key])))
    bu_sum = {key: sum((Decimal(str(by_bu[unit][key])) for unit in BUSINESS_UNITS), Decimal(0)) for key in ("planned_fte", "required_fte", "loaded_cost", "capacity_gap")}
    role_sum = {key: sum((Decimal(str(by_role[role][key])) for role in ROLE_GROUPS), Decimal(0)) for key in ("planned_fte", "required_fte", "loaded_cost", "capacity_gap")}
    residuals = [abs(Decimal(str(portfolio[key])) - bu_sum[key]) for key in bu_sum] + [abs(Decimal(str(portfolio[key])) - role_sum[key]) for key in role_sum]
    residual = max(residuals, default=Decimal(0))
    evidence = {"status": "reconciled" if residual <= TOLERANCE else "not_reconciled", "tolerance_rmb_millions": float(TOLERANCE), "residual": float(residual), "max_residual": float(residual), "no_double_counting": residual <= TOLERANCE, "portfolio_equals_business_units": residual <= TOLERANCE, "business_units_equal_role_groups": residual <= TOLERANCE}
    return {"case_id": case.case_id, "as_of_date": case.metadata["as_of_date"], "currency": "RMB", "unit": "RMB millions unless stated otherwise", "plan_variant": selected_variant, "headcount_rows": output, "locked_rows": locked, "rollups": {"role_group": by_role, "business_unit": by_bu, "role_group_business_unit": nested, "portfolio": portfolio}, "selected_vs_base_delta": deltas, "reconciliation_evidence": evidence, "provenance": "calculated", "input_provenance": "synthetic_plan", "disclosure": "Headcount, payroll cost, and capacity are deterministic synthetic planning data; not MINISO reported or internal payroll/HRIS data."}


def _rollup(rows):
    planned = sum((_dec(r["planned_fte"]) for r in rows), Decimal(0)); required = sum((_dec(r["required_fte"]) for r in rows), Decimal(0)); loaded = sum((_dec(r["loaded_cost"]) for r in rows), Decimal(0)); gap = sum((_dec(r["capacity_gap"]) for r in rows), Decimal(0))
    return {"planned_fte": float(planned), "required_fte": float(required), "loaded_cost": float(loaded), "capacity_gap": float(gap), "row_count": len(rows), "provenance": "calculated"}
