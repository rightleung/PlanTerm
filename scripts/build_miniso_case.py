#!/usr/bin/env python3
"""Build or check the deterministic MINISO planning records."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/source/miniso_public_actuals.json"
CASE_DIR = ROOT / "data/cases/miniso-2026"
OUTPUT = CASE_DIR / "planning_records.csv"
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
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assumptions = json.loads((CASE_DIR / "assumptions.json").read_text(encoding="utf-8"))
    weights = assumptions["monthly_seasonality"]
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

    def metric_totals_for_h1(period: str, revenue: dict[str, float], scenario: str) -> dict[str, dict[str, float]]:
        total_revenue = get_metric(snapshot, period, "Revenue")
        gp = get_metric(snapshot, period, "Gross Profit")
        op = get_metric(snapshot, period, "Operating Profit")
        result = {}
        for unit in UNITS:
            share = revenue[unit] / sum(revenue.values())
            result[unit] = {"revenue": revenue[unit], "gross_profit": gp * share, "cost_of_sales": (total_revenue - gp) * share, "operating_profit": op * share}
            result[unit]["operating_expense"] = result[unit]["gross_profit"] - result[unit]["operating_profit"]
        return result

    actual26 = metric_totals_for_h1("2026 H1", h1_26_revenue, "actual")
    prior25_h1 = metric_totals_for_h1("2025 H1", h1_25_revenue, "prior_year")
    fy25_total = metric_totals_for_h1("FY2025", fy25_revenue, "prior_year")
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
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit("planning_records.csv differs from deterministic generator output")
        print(f"Case check passed: {OUTPUT}")
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {len(rows)} planning records to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
