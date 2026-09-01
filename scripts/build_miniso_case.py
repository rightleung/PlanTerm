#!/usr/bin/env python3
"""Build or check the deterministic MINISO planning records."""

from __future__ import annotations

import argparse
import csv
import math
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.committed_json import load_committed_json


SNAPSHOT = ROOT / "data/source/miniso_public_actuals.json"
CASE_DIR = ROOT / "data/cases/miniso-2026"
OUTPUT = CASE_DIR / "planning_records.csv"
CATEGORY_SEED_OUTPUT = CASE_DIR / "category_scenario_seed.csv"
FIELDS = ["period", "scenario", "brand", "market", "business_unit", "metric", "value", "unit", "provenance"]
MONTHS = [f"2026-{month:02d}" for month in range(1, 13)]
H1 = set(MONTHS[:6])
H2 = set(MONTHS[6:])
UNITS = ["MINISO - Chinese Mainland", "MINISO - Overseas", "TOP TOY - Global"]
UNIT_MAP = {
    "MINISO - Chinese Mainland": ("MINISO", "mainland", "MINISO Mainland"),
    "MINISO - Overseas": ("MINISO", "overseas", "MINISO Overseas"),
    "TOP TOY - Global": ("TOP_TOY", "global", "TOP TOY"),
}
METRIC_UNITS = {
    "revenue": "RMB millions", "volume": "million transactions", "average_ticket": "RMB per transaction",
    "cost_of_sales": "RMB millions", "gross_profit": "RMB millions", "operating_expense": "RMB millions", "operating_profit": "RMB millions",
}


def allocate(total: float, months: list[str], weights: dict[str, float]) -> dict[str, float]:
    raw = {month: total * weights[month] / sum(weights[m] for m in months) for month in months}
    last = months[-1]
    raw[last] += total - sum(raw.values())
    return raw


def add_row(rows: list[dict], period: str, scenario: str, unit: str, metric: str, value: float | None, provenance: str):
    brand, market, _ = UNIT_MAP[unit]
    rows.append({"period": period, "scenario": scenario, "brand": brand, "market": market, "business_unit": unit, "metric": metric, "value": "" if value is None else f"{value:.6f}", "unit": METRIC_UNITS[metric], "provenance": provenance})


def get_split(snapshot: dict, period: str) -> dict[str, float]:
    return snapshot["periods"][period]["revenue_split"]


def get_metric(snapshot: dict, period: str, metric: str) -> float:
    return snapshot["periods"][period]["metrics"][metric]


def build_rows() -> list[dict]:
    snapshot = load_committed_json(SNAPSHOT)
    assumptions = load_committed_json(CASE_DIR / "assumptions.json")
    weights = assumptions["monthly_seasonality"]
    profit_indices = assumptions["profit_allocation_indices"]
    rows: list[dict] = []

    fy25_revenue = {unit: get_split(snapshot, "FY2025")[source] for unit, (_, _, source) in UNIT_MAP.items()}
    h1_25_revenue = {unit: get_split(snapshot, "2025 H1")[source] for unit, (_, _, source) in UNIT_MAP.items()}
    h1_26_revenue = {unit: get_split(snapshot, "2026 H1")[source] for unit, (_, _, source) in UNIT_MAP.items()}
    # The MVP has three business units, so the immaterial reported "Others"
    # revenue is transparently allocated to MINISO Mainland.
    for period, target in (("FY2025", fy25_revenue), ("2025 H1", h1_25_revenue), ("2026 H1", h1_26_revenue)):
        target["MINISO - Chinese Mainland"] += get_split(snapshot, period).get("Others", 0.0)
    budget_revenue = {unit: fy25_revenue[unit] * (1 + assumptions["budget_assumptions"][unit]["revenue_growth_vs_fy2025"]) for unit in UNITS}
    forecast_revenue = {unit: h1_26_revenue[unit] + budget_revenue[unit] * 0.52 * (1 + assumptions["h2_forecast_adjustment_vs_budget"][unit]) for unit in UNITS}

    def normalized_index_weights(revenue: dict[str, float], index_name: str) -> dict[str, float]:
        indexed = {unit: revenue[unit] * profit_indices[unit][index_name] for unit in UNITS}
        if any(value <= 0 for value in indexed.values()) or sum(indexed.values()) <= 0:
            raise ValueError(f"Invalid {index_name} values for profit allocation")
        total = sum(indexed.values())
        return {unit: value / total for unit, value in indexed.items()}

    def metric_totals_for_h1(period: str, revenue: dict[str, float]) -> dict[str, dict[str, float]]:
        total_revenue = get_metric(snapshot, period, "Revenue")
        gp = get_metric(snapshot, period, "Gross Profit")
        op = get_metric(snapshot, period, "Operating Profit")
        gross_profit_weights = normalized_index_weights(revenue, "gross_margin_index")
        operating_profit_weights = normalized_index_weights(revenue, "operating_margin_index")
        result = {}
        for unit in UNITS:
            result[unit] = {
                "revenue": revenue[unit],
                "gross_profit": gp * gross_profit_weights[unit],
                "cost_of_sales": revenue[unit] - gp * gross_profit_weights[unit],
                "operating_profit": op * operating_profit_weights[unit],
            }
            result[unit]["operating_expense"] = result[unit]["gross_profit"] - result[unit]["operating_profit"]
            if result[unit]["cost_of_sales"] < 0 or result[unit]["operating_expense"] < 0 or result[unit]["gross_profit"] > result[unit]["revenue"]:
                raise ValueError(f"Invalid profit allocation for {period} / {unit}")
        return result

    actual26 = metric_totals_for_h1("2026 H1", h1_26_revenue)
    prior25_h1 = metric_totals_for_h1("2025 H1", h1_25_revenue)
    fy25_total = metric_totals_for_h1("FY2025", fy25_revenue)
    budget_total = {}
    for unit in UNITS:
        assumption = assumptions["budget_assumptions"][unit]
        revenue = budget_revenue[unit]
        gp = revenue * assumption["budget_gross_margin"]
        op = revenue * assumption["budget_operating_margin"]
        budget_total[unit] = {"revenue": revenue, "gross_profit": gp, "cost_of_sales": revenue - gp, "operating_profit": op, "operating_expense": gp - op}
    forecast_total = {}
    for unit in UNITS:
        h1 = actual26[unit]
        h2_budget = {metric: budget_total[unit][metric] * 0.52 for metric in budget_total[unit]}
        adjustment = assumptions["h2_forecast_adjustment_vs_budget"][unit]
        forecast_total[unit] = {"revenue": h1["revenue"] + h2_budget["revenue"] * (1 + adjustment)}
        forecast_total[unit]["gross_profit"] = h1["gross_profit"] + h2_budget["gross_profit"] * (1 + adjustment)
        forecast_total[unit]["cost_of_sales"] = forecast_total[unit]["revenue"] - forecast_total[unit]["gross_profit"]
        forecast_total[unit]["operating_profit"] = h1["operating_profit"] + h2_budget["operating_profit"] * (1 + adjustment)
        forecast_total[unit]["operating_expense"] = forecast_total[unit]["gross_profit"] - forecast_total[unit]["operating_profit"]

    # Actual YTD is anchored to the official H1 total; only YTD months exist.
    for unit in UNITS:
        budget_ticket = assumptions["budget_assumptions"][unit]["average_ticket"]
        actual_ticket = budget_ticket * assumptions["actual_ticket_factors_vs_budget"][unit]
        for month, revenue in allocate(actual26[unit]["revenue"], MONTHS[:6], weights).items():
            share = revenue / actual26[unit]["revenue"]
            for metric in ("revenue", "gross_profit", "cost_of_sales", "operating_expense", "operating_profit"):
                add_row(rows, month, "actual", unit, metric, actual26[unit][metric] * share, "synthetic_allocation")
            add_row(rows, month, "actual", unit, "average_ticket", actual_ticket, "synthetic_allocation")
            add_row(rows, month, "actual", unit, "volume", revenue / actual_ticket, "calculated")

        # Budget covers the full planning year.
        for month, revenue in allocate(budget_total[unit]["revenue"], MONTHS, weights).items():
            share = revenue / budget_total[unit]["revenue"]
            for metric in ("revenue", "gross_profit", "cost_of_sales", "operating_expense", "operating_profit"):
                add_row(rows, month, "budget", unit, metric, budget_total[unit][metric] * share, "synthetic_plan")
            add_row(rows, month, "budget", unit, "average_ticket", budget_ticket, "synthetic_plan")
            add_row(rows, month, "budget", unit, "volume", revenue / budget_ticket, "calculated")

        # Forecast uses actual H1 and an adjusted H2 latest estimate.
        h2_forecast = {metric: forecast_total[unit][metric] - actual26[unit][metric] for metric in forecast_total[unit]}
        for month, revenue in allocate(actual26[unit]["revenue"], MONTHS[:6], weights).items():
            share = revenue / actual26[unit]["revenue"]
            for metric in ("revenue", "gross_profit", "cost_of_sales", "operating_expense", "operating_profit"):
                add_row(rows, month, "forecast", unit, metric, actual26[unit][metric] * share, "calculated")
            add_row(rows, month, "forecast", unit, "average_ticket", actual_ticket, "calculated")
            add_row(rows, month, "forecast", unit, "volume", revenue / actual_ticket, "calculated")
        for month, revenue in allocate(h2_forecast["revenue"], MONTHS[6:], weights).items():
            share = revenue / h2_forecast["revenue"]
            for metric in ("revenue", "gross_profit", "cost_of_sales", "operating_expense", "operating_profit"):
                add_row(rows, month, "forecast", unit, metric, h2_forecast[metric] * share, "synthetic_plan")
            add_row(rows, month, "forecast", unit, "average_ticket", budget_ticket, "synthetic_plan")
            add_row(rows, month, "forecast", unit, "volume", revenue / budget_ticket, "calculated")

        # Prior year maps 2025 full-year data into 2026 comparison months while preserving H1 and FY anchors.
        for month, revenue in {**allocate(prior25_h1[unit]["revenue"], MONTHS[:6], weights), **allocate(fy25_total[unit]["revenue"] - prior25_h1[unit]["revenue"], MONTHS[6:], weights)}.items():
            base = prior25_h1[unit] if month in H1 else {metric: fy25_total[unit][metric] - prior25_h1[unit][metric] for metric in fy25_total[unit]}
            share = revenue / base["revenue"]
            prior_ticket = budget_ticket * 0.96 if unit == "MINISO - Chinese Mainland" else budget_ticket * 0.98 if unit == "MINISO - Overseas" else budget_ticket * 0.95
            for metric in ("revenue", "gross_profit", "cost_of_sales", "operating_expense", "operating_profit"):
                add_row(rows, month, "prior_year", unit, metric, base[metric] * share, "synthetic_allocation")
            add_row(rows, month, "prior_year", unit, "average_ticket", prior_ticket, "synthetic_allocation")
            add_row(rows, month, "prior_year", unit, "volume", revenue / prior_ticket, "calculated")

    validate(rows, snapshot)
    return rows


CATEGORY_FIELDS = ["case_id", "plan_variant", "period", "business_unit", "category_id", "volume_change_pct", "average_ticket_change_pct", "gross_margin_delta_pp", "opex_ratio_delta_pp"]
HARMONIZED = {
    "MINISO - Chinese Mainland": ["miniso_ip_toys", "miniso_home_lifestyle", "miniso_beauty_personal_care", "miniso_electronics_accessories", "miniso_stationery_food_other"],
    "MINISO - Overseas": ["miniso_ip_toys", "miniso_home_lifestyle", "miniso_beauty_personal_care", "miniso_electronics_accessories", "miniso_stationery_food_other"],
    "TOP TOY - Global": ["toptoy_blind_boxes_figures", "toptoy_building_blocks_kits", "toptoy_plush_dolls_sculptures", "toptoy_other"],
}


def build_category_seed() -> list[dict]:
    assumptions = load_committed_json(CASE_DIR / "assumptions.json")
    shares = assumptions.get("category_revenue_shares", {})
    for unit, categories in HARMONIZED.items():
        if sum(Decimal(str(shares[unit][category]["budget"])) for category in categories) != Decimal(1):
            raise ValueError(f"Category budget shares do not reconcile for {unit}")
        for index_name in ("category_ticket_indices", "category_gross_margin_indices", "category_opex_ratio_indices"):
            weighted = sum(Decimal(str(shares[unit][category]["budget"])) * Decimal(str(assumptions[index_name][category])) for category in categories)
            if weighted <= 0 or any(Decimal(str(assumptions[index_name][category])) <= 0 for category in categories):
                raise ValueError(f"Invalid normalized {index_name} for {unit}")
    records = build_rows()
    anchors = {(r["scenario"], r["period"], r["business_unit"], r["metric"]): (None if r["value"] == "" else Decimal(r["value"])) for r in records}
    rows: list[dict] = []
    variants = assumptions["variant_driver_adjustments"]
    def driver(unit: str, period: str) -> dict[str, Decimal]:
        budget_rev = anchors[("budget", period, unit, "revenue")]
        forecast_rev = anchors[("forecast", period, unit, "revenue")]
        budget_vol = anchors[("budget", period, unit, "volume")]
        forecast_vol = anchors[("forecast", period, unit, "volume")]
        budget_ticket = anchors[("budget", period, unit, "average_ticket")]
        forecast_ticket = anchors[("forecast", period, unit, "average_ticket")]
        budget_gm = anchors[("budget", period, unit, "gross_profit")] / budget_rev
        forecast_gm = anchors[("forecast", period, unit, "gross_profit")] / forecast_rev
        budget_opex = anchors[("budget", period, unit, "operating_expense")] / budget_rev
        forecast_opex = anchors[("forecast", period, unit, "operating_expense")] / forecast_rev
        return {
            "volume_change_pct": forecast_vol / budget_vol - 1,
            "average_ticket_change_pct": forecast_ticket / budget_ticket - 1,
            "gross_margin_delta_pp": forecast_gm - budget_gm,
            "opex_ratio_delta_pp": forecast_opex - budget_opex,
        }
    for variant in ("base", "upside", "downside"):
        for period in sorted(H2):
            for unit in UNITS:
                for category_id in HARMONIZED[unit]:
                    base = driver(unit, period)
                    row = {
                        "case_id": "miniso-2026", "plan_variant": variant, "period": period,
                        "business_unit": unit, "category_id": category_id,
                        "volume_change_pct": f"{base['volume_change_pct'] + Decimal(str(variants[variant]['volume_change_pct'])):.6f}",
                        "average_ticket_change_pct": f"{base['average_ticket_change_pct'] + Decimal(str(variants[variant]['average_ticket_change_pct'])):.6f}",
                        "gross_margin_delta_pp": f"{base['gross_margin_delta_pp'] + Decimal(str(variants[variant]['gross_margin_delta_pp'])):.6f}",
                        "opex_ratio_delta_pp": f"{base['opex_ratio_delta_pp'] + Decimal(str(variants[variant]['opex_ratio_delta_pp'])):.6f}",
                    }
                    rows.append(row)
    validate_category_seed_volume(rows, anchors, assumptions)
    return rows


def validate_category_seed_volume(rows: list[dict], anchors: dict, assumptions: dict) -> None:
    """Independently verify all default leaf volumes against BU parent anchors."""
    by_key = {(row["plan_variant"], row["period"], row["business_unit"], row["category_id"]): row for row in rows}
    tolerance = Decimal("0.01")
    for variant in ("base", "upside", "downside"):
        adjustment = Decimal(str(assumptions["variant_driver_adjustments"][variant]["volume_change_pct"]))
        for period in sorted(H2):
            for unit, category_ids in HARMONIZED.items():
                budget_revenue = anchors[("budget", period, unit, "revenue")]
                budget_ticket = anchors[("budget", period, unit, "average_ticket")]
                harmonic_scale = sum((
                    Decimal(str(assumptions["category_revenue_shares"][unit][category_id]["budget"])) /
                    Decimal(str(assumptions["category_ticket_indices"][category_id]))
                    for category_id in category_ids
                ), Decimal(0))
                leaf_volume = sum((
                    budget_revenue * Decimal(str(assumptions["category_revenue_shares"][unit][category_id]["budget"])) /
                    (budget_ticket * Decimal(str(assumptions["category_ticket_indices"][category_id])) * harmonic_scale) *
                    (Decimal(1) + Decimal(by_key[(variant, period, unit, category_id)]["volume_change_pct"]))
                    for category_id in category_ids
                ), Decimal(0))
                expected = anchors[("forecast", period, unit, "volume")] + adjustment * anchors[("budget", period, unit, "volume")]
                if abs(leaf_volume - expected) > tolerance:
                    raise ValueError(f"Category volume does not reconcile: {variant}/{period}/{unit}: {leaf_volume} != {expected}")


def validate(rows: list[dict], snapshot: dict):
    by_key = {(row["scenario"], row["period"], row["business_unit"], row["metric"]): (None if row["value"] == "" else float(row["value"])) for row in rows}
    actual_h1 = sum(by_key[("actual", month, unit, "revenue")] for month in MONTHS[:6] for unit in UNITS)
    assert math.isclose(actual_h1, snapshot["periods"]["2026 H1"]["metrics"]["Revenue"], abs_tol=0.01)
    assert all(not (row["scenario"] == "actual" and row["period"] > "2026-06") for row in rows)
    for scenario in ("actual", "budget", "forecast", "prior_year"):
        periods = MONTHS[:6] if scenario == "actual" else MONTHS
        for period in periods:
            for unit in UNITS:
                revenue = by_key[(scenario, period, unit, "revenue")]
                volume = by_key[(scenario, period, unit, "volume")]
                ticket = by_key[(scenario, period, unit, "average_ticket")]
                assert math.isclose(revenue, volume * ticket, abs_tol=0.01)
                gp = by_key[(scenario, period, unit, "gross_profit")]
                cos = by_key[(scenario, period, unit, "cost_of_sales")]
                op = by_key[(scenario, period, unit, "operating_profit")]
                opex = by_key[(scenario, period, unit, "operating_expense")]
                assert math.isclose(gp, revenue - cos, abs_tol=0.01)
                assert math.isclose(op, gp - opex, abs_tol=0.01)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed CSV matches deterministic output")
    args = parser.parse_args()
    rows = build_rows()
    # csv.DictWriter expects a file-like object; use an in-memory text buffer.
    import io
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue()
    category_buffer = io.StringIO()
    category_writer = csv.DictWriter(category_buffer, fieldnames=CATEGORY_FIELDS, lineterminator="\n")
    category_writer.writeheader()
    category_writer.writerows(build_category_seed())
    category_content = category_buffer.getvalue()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit("planning_records.csv differs from deterministic generator output")
        if not CATEGORY_SEED_OUTPUT.exists() or CATEGORY_SEED_OUTPUT.read_text(encoding="utf-8") != category_content:
            raise SystemExit("category_scenario_seed.csv differs from deterministic generator output")
        print(f"Case check passed: {OUTPUT} ({len(rows)} planning rows); {CATEGORY_SEED_OUTPUT} ({len(build_category_seed())} category rows)")
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    CATEGORY_SEED_OUTPUT.write_text(category_content, encoding="utf-8")
    print(f"Wrote {len(rows)} planning records to {OUTPUT}; {len(build_category_seed())} category seed rows to {CATEGORY_SEED_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
