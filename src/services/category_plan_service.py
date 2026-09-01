"""Deterministic category scenario calculations and reconciliation gates."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, getcontext

from src.repositories.case_repository import CaseData
from src.services.csv_input_service import H2_MONTHS

getcontext().prec = 40
TOLERANCE = Decimal("0.01")
VARIANTS = ("base", "upside", "downside")


class ReconciliationError(ValueError):
    pass


def _dec(value) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def _metric(case, scenario, unit, period, metric):
    return sum((_dec(r.value) for r in case.records if r.scenario.value == scenario and r.business_unit == unit and r.period == period and r.metric == metric), Decimal(0))


def _h1(case, unit, metric):
    return sum((_dec(r.value) for r in case.records if r.scenario.value == "actual" and r.business_unit == unit and r.period <= "2026-06" and r.metric == metric), Decimal(0))


def _idx(assumptions, category_id, name):
    value = assumptions.get(name, {}).get(category_id)
    if value is None:
        raise ReconciliationError(f"Missing committed category index: {name}/{category_id}")
    return _dec(value)


def _normalization(assumptions):
    """Validate the single committed category-index normalization schema."""
    normalization = assumptions.get("category_index_normalization")
    expected = {
        "ticket": ("harmonic_volume_preserving", "category_ticket_indices"),
        "gross_margin": ("revenue_share_weighted", "category_gross_margin_indices"),
        "opex_ratio": ("revenue_share_weighted", "category_opex_ratio_indices"),
    }
    if not isinstance(normalization, dict):
        raise ReconciliationError("Missing category index normalization schema")
    for metric, (method, index) in expected.items():
        config = normalization.get(metric)
        if not isinstance(config, dict) or config.get("method") != method or config.get("index") != index:
            raise ReconciliationError(f"Invalid category index normalization for {metric}")
    tolerance = _dec(normalization.get("residual_tolerance_rmb_millions"))
    if tolerance != TOLERANCE:
        raise ReconciliationError("Invalid category normalization tolerance")
    return normalization


def _baseline(case, unit, period, category_id):
    assumptions = case.assumptions
    _normalization(assumptions)
    shares = assumptions.get("category_revenue_shares", {}).get(unit, {})
    item = shares.get(category_id)
    if not item or "budget" not in item:
        raise ReconciliationError(f"Missing committed category baseline: {unit}/{category_id}")
    categories = [x for x in (case.taxonomy or {}).get("categories", []) if x["business_unit"] == unit]
    if not categories or sum((_dec(shares.get(x["category_id"], {}).get("budget")) for x in categories), Decimal(0)) != Decimal(1):
        raise ReconciliationError(f"Category budget shares do not reconcile for {unit}")
    # Revenue shares allocate revenue.  Normalizing ticket indices harmonically
    # preserves both that revenue split and the independent parent volume anchor:
    # Σ(revenue_share / (ticket_index × harmonic_scale)) == 1.
    ticket_scale = sum((
        _dec(shares[x["category_id"]]["budget"]) / _idx(assumptions, x["category_id"], "category_ticket_indices")
        for x in categories
    ), Decimal(0))
    if ticket_scale <= 0:
        raise ReconciliationError(f"Invalid harmonic ticket normalization for {unit}")
    weights = {}
    for name in ("category_gross_margin_indices", "category_opex_ratio_indices"):
        weights[name] = sum((_dec(shares[x["category_id"]]["budget"]) * _idx(assumptions, x["category_id"], name) for x in categories), Decimal(0))
        if weights[name] <= 0:
            raise ReconciliationError(f"Invalid category index normalization for {unit}")
    bu_revenue = _metric(case, "budget", unit, period, "revenue")
    bu_ticket = _metric(case, "budget", unit, period, "average_ticket")
    bu_gp = _metric(case, "budget", unit, period, "gross_profit")
    bu_opex = _metric(case, "budget", unit, period, "operating_expense")
    share = _dec(item["budget"])
    ticket = bu_ticket * _idx(assumptions, category_id, "category_ticket_indices") * ticket_scale
    revenue = bu_revenue * share
    return {
        "revenue": revenue,
        "ticket": ticket,
        "volume": revenue / ticket if ticket else Decimal(0),
        "gross_margin": (bu_gp / bu_revenue if bu_revenue else Decimal(0)) * _idx(assumptions, category_id, "category_gross_margin_indices") / weights["category_gross_margin_indices"],
        "opex_ratio": (bu_opex / bu_revenue if bu_revenue else Decimal(0)) * _idx(assumptions, category_id, "category_opex_ratio_indices") / weights["category_opex_ratio_indices"],
    }


def _close(actual, expected, label):
    if abs(actual - expected) > TOLERANCE:
        raise ReconciliationError(f"{label}: {actual} != {expected}")


def is_committed_variant_seed(case, rows, variant: str) -> bool:
    """Whether one plan variant still matches its deterministic committed seed."""
    fields = ("volume_change_pct", "average_ticket_change_pct", "gross_margin_delta_pp", "opex_ratio_delta_pp")
    committed = {
        (item["plan_variant"], item["period"], item["business_unit"], item["category_id"]): tuple(_dec(item[field]) for field in fields)
        for item in case.category_seed
        if item["plan_variant"] == variant
    }
    supplied = {
        (row.plan_variant.value, row.period, row.business_unit, row.category_id): tuple(_dec(getattr(row, field)) for field in fields)
        for row in rows
        if row.plan_variant.value == variant
    }
    return supplied == committed


def _is_committed_seed(case, rows) -> bool:
    """Whether every variant in the full matrix is the exact committed seed."""
    return all(is_committed_variant_seed(case, rows, variant) for variant in VARIANTS)


def _category_context(case, categories):
    """Return disclosed synthetic category allocations for locked comparison context."""
    context = []
    scenarios = {
        "h1_actual": ("actual", lambda unit, category_id: _dec(case.assumptions["category_revenue_shares"][unit][category_id]["actual"])),
        "h1_prior_year": ("prior_year", lambda unit, category_id: _dec(case.assumptions["category_revenue_shares"][unit][category_id]["actual"])),
        "fy_budget": ("budget", lambda unit, category_id: _dec(case.assumptions["category_revenue_shares"][unit][category_id]["budget"])),
    }
    metrics = ("revenue", "volume", "gross_profit", "cost_of_sales", "operating_expense", "operating_profit")
    for category in categories:
        unit, category_id = category["business_unit"], category["category_id"]
        values = {}
        for field, (scenario, share_for) in scenarios.items():
            selected_periods = (
                [f"2026-{month:02d}" for month in range(1, 7)]
                if field != "fy_budget"
                else [f"2026-{month:02d}" for month in range(1, 13)]
            )
            share = share_for(unit, category_id)
            allocation = {
                metric: sum((_metric(case, scenario, unit, period, metric) for period in selected_periods), Decimal(0)) * share
                for metric in metrics
            }
            revenue = allocation["revenue"]
            values[field] = {
                **{metric: float(value) for metric, value in allocation.items()},
                "average_ticket": float(revenue / allocation["volume"]) if allocation["volume"] else None,
                "gross_margin_pct": float(allocation["gross_profit"] / revenue) if revenue else None,
                "opex_ratio_pct": float(allocation["operating_expense"] / revenue) if revenue else None,
                "operating_margin_pct": float(allocation["operating_profit"] / revenue) if revenue else None,
            }
        context.append({
            "business_unit": unit,
            "category_id": category_id,
            "category_name": category["category_name"],
            "provenance": "synthetic_allocation",
            "allocation_basis": "committed_category_revenue_share",
            **values,
        })
    return context


def calculate_rows(case: CaseData, rows: list, selected_variant: str):
    if selected_variant not in VARIANTS:
        raise ReconciliationError("Unknown selected plan variant")
    categories = (case.taxonomy or {}).get("categories", [])
    pairs = {(x["business_unit"], x["category_id"]) for x in categories}
    if len(rows) != 252 or {(r.business_unit, r.category_id) for r in rows} != pairs or {r.plan_variant.value for r in rows} != set(VARIANTS) or {r.period for r in rows} != H2_MONTHS:
        raise ReconciliationError("Complete scenario matrix failed schema reconciliation")
    details, totals = [], defaultdict(lambda: defaultdict(Decimal))
    for row in rows:
        base = _baseline(case, row.business_unit, row.period, row.category_id)
        volume = base["volume"] * (1 + _dec(row.volume_change_pct))
        ticket = base["ticket"] * (1 + _dec(row.average_ticket_change_pct))
        gm = base["gross_margin"] + _dec(row.gross_margin_delta_pp)
        opex_ratio = base["opex_ratio"] + _dec(row.opex_ratio_delta_pp)
        if volume <= 0 or ticket <= 0 or not (Decimal(0) <= gm <= Decimal(1)) or not (Decimal(0) <= opex_ratio <= Decimal(1)):
            raise ReconciliationError("Scenario metric outside valid bounds")
        revenue, gp = volume * ticket, volume * ticket * gm
        opex, op = revenue * opex_ratio, revenue * (gm - opex_ratio)
        cos = revenue - gp
        key = (row.plan_variant.value, row.period, row.business_unit)
        for metric, value in (("revenue", revenue), ("volume", volume), ("gross_profit", gp), ("cost_of_sales", cos), ("operating_expense", opex), ("operating_profit", op)):
            totals[key][metric] += value
        details.append({"period": row.period, "plan_variant": row.plan_variant.value, "business_unit": row.business_unit, "category_id": row.category_id, "category_name": row.category_name, "volume": float(volume), "average_ticket": float(ticket), "revenue": float(revenue), "gross_profit": float(gp), "cost_of_sales": float(cos), "operating_expense": float(opex), "operating_profit": float(op), "revenue_mix_pct": float(_dec(case.assumptions["category_revenue_shares"][row.business_unit][row.category_id]["budget"])), "gross_margin_pct": float(gm), "opex_ratio_pct": float(opex_ratio), "operating_margin_pct": float(op / revenue if revenue else 0), "provenance": "calculated"})

    units = sorted({x[0] for x in pairs})
    metrics = ("revenue", "volume", "gross_profit", "cost_of_sales", "operating_expense", "operating_profit")
    committed_variants = {variant: is_committed_variant_seed(case, rows, variant) for variant in VARIANTS}
    for variant in VARIANTS:
        portfolio = defaultdict(Decimal)
        for unit in units:
            # A committed Base seed is tied to the public forecast anchor. Once
            # a user edits Base, the scenario is still valid but must reconcile
            # to its own recalculated roll-up rather than the old anchor.
            if variant == "base" and committed_variants["base"]:
                for period in H2_MONTHS:
                    for metric in metrics:
                        _close(totals[(variant, period, unit)][metric], _metric(case, "forecast", unit, period, metric), f"Base {unit} {period} {metric} reconciliation")
            if committed_variants[variant]:
                adjustment = _dec(case.assumptions["variant_driver_adjustments"][variant]["volume_change_pct"])
                for period in H2_MONTHS:
                    expected_volume = _metric(case, "forecast", unit, period, "volume") + adjustment * _metric(case, "budget", unit, period, "volume")
                    _close(totals[(variant, period, unit)]["volume"], expected_volume, f"Committed {variant} {unit} {period} volume reconciliation")
            bu = {metric: sum((totals[(variant, period, unit)][metric] for period in H2_MONTHS), Decimal(0)) for metric in metrics}
            for metric in metrics:
                portfolio[metric] += bu[metric]
                if variant == "base" and committed_variants["base"]:
                    expected = sum((_metric(case, "forecast", unit, period, metric) for period in H2_MONTHS), Decimal(0))
                    _close(bu[metric], expected, f"Base H2 {unit} {metric} reconciliation")
        for metric in metrics:
            _close(portfolio[metric], sum((sum((totals[(variant, period, unit)][metric] for period in H2_MONTHS), Decimal(0)) for unit in units), Decimal(0)), f"Portfolio {variant} {metric} reconciliation")
            if variant == "base" and committed_variants["base"]:
                anchor = sum((_metric(case, "forecast", unit, period, metric) for unit in units for period in H2_MONTHS), Decimal(0))
                _close(portfolio[metric], anchor, f"Base H2 portfolio {metric} reconciliation")

    fy_details = []
    for variant in VARIANTS:
        for unit in units:
            h2 = {metric: sum((totals[(variant, period, unit)][metric] for period in H2_MONTHS), Decimal(0)) for metric in metrics}
            fy = {metric: _h1(case, unit, metric) + h2[metric] for metric in metrics}
            unit_rows = []
            for cat in [x for x in categories if x["business_unit"] == unit]:
                cat_id = cat["category_id"]
                share = _dec(case.assumptions["category_revenue_shares"][unit][cat_id]["actual"])
                values = {metric: _h1(case, unit, metric) * share + sum((_dec(d[metric]) for d in details if d["plan_variant"] == variant and d["business_unit"] == unit and d["category_id"] == cat_id), Decimal(0)) for metric in metrics}
                item = {"period": "FY2026", "plan_variant": variant, "business_unit": unit, "category_id": cat_id, "category_name": cat["category_name"], "volume": None, "average_ticket": None, **{metric: float(value) for metric, value in values.items()}, "revenue_mix_pct": float(values["revenue"] / fy["revenue"] if fy["revenue"] else 0), "gross_margin_pct": float(values["gross_profit"] / values["revenue"] if values["revenue"] else 0), "opex_ratio_pct": float(values["operating_expense"] / values["revenue"] if values["revenue"] else 0), "operating_margin_pct": float(values["operating_profit"] / values["revenue"] if values["revenue"] else 0), "provenance": "calculated"}
                fy_details.append(item); unit_rows.append(item)
            for metric in metrics:
                _close(sum((_dec(d[metric]) for d in unit_rows), Decimal(0)), fy[metric], f"FY {variant} {unit} {metric} reconciliation")
    details.extend(fy_details)
    comparison = {"selected_plan_variant": selected_variant}
    for metric in ("revenue", "gross_profit", "operating_profit"):
        base = sum((_dec(d[metric]) for d in fy_details if d["plan_variant"] == "base"), Decimal(0))
        selected = sum((_dec(d[metric]) for d in fy_details if d["plan_variant"] == selected_variant), Decimal(0))
        comparison[metric] = {"base_fy_forecast": float(base), "selected_fy_forecast": float(selected), "delta": float(selected - base), "unit": "RMB millions"}
    return details, comparison, _category_context(case, categories)
