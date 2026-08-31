"""Pydantic contracts for the PlanTerm planning and analysis API."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Scenario(str, Enum):
    ACTUAL = "actual"
    BUDGET = "budget"
    FORECAST = "forecast"
    PRIOR_YEAR = "prior_year"


class Provenance(str, Enum):
    PUBLIC_REPORTED = "public_reported"
    SYNTHETIC_ALLOCATION = "synthetic_allocation"
    SYNTHETIC_PLAN = "synthetic_plan"
    CALCULATED = "calculated"


class PlanningRecord(BaseModel):
    period: str
    scenario: Scenario
    brand: Literal["MINISO", "TOP_TOY"]
    market: Literal["mainland", "overseas", "global"]
    business_unit: str
    metric: str
    value: float | None = None
    unit: str
    provenance: Provenance


class KpiSnapshot(BaseModel):
    metric: str
    label: str
    unit: str
    actual_ytd: float | None
    budget_ytd: float | None
    variance_amount: float | None
    variance_pct: float | None
    prior_year_ytd: float | None
    yoy_pct: float | None
    fy_budget: float | None
    fy_forecast: float | None
    forecast_gap: float | None
    status: Literal["Favorable", "Unfavorable", "Neutral"] | None


class VarianceRow(BaseModel):
    business_unit: str
    brand: str
    market: str
    revenue_actual: float | None
    revenue_budget: float | None
    revenue_variance: float | None
    revenue_variance_pct: float | None
    gross_profit_actual: float | None
    gross_profit_budget: float | None
    operating_profit_actual: float | None
    operating_profit_budget: float | None
    operating_margin_actual: float | None
    operating_margin_budget: float | None
    operating_expense_actual: float | None
    operating_expense_budget: float | None
    forecast_gap: float | None
    price_amount: float | None
    volume_amount: float | None
    mix_amount: float | None
    primary_driver: str | None
    status: Literal["Favorable", "Unfavorable", "Neutral"] | None


class PvmBridge(BaseModel):
    actual_revenue: float | None
    budget_revenue: float | None
    volume: float | None
    mix: float | None
    price: float | None
    reconciliation_difference: float | None
    unit: str = "RMB millions"


class ManagementInsight(BaseModel):
    title: str
    business_unit: str
    severity: Literal["watch", "positive"]
    message: str
    driver: str
    driver_amount: float | None
    forecast_gap: float | None
    action: str


class MonthlyTrendPoint(BaseModel):
    period: str
    actual: float | None
    budget: float | None
    forecast: float | None
    prior_year: float | None


class DataSource(BaseModel):
    name: str
    url: str
    source_date: str
    scope: str


class PlanningDashboardResponse(BaseModel):
    metadata: dict
    assumptions: dict
    available_filters: dict
    selected_filters: dict
    kpis: list[KpiSnapshot]
    monthly_trend: list[MonthlyTrendPoint]
    business_unit_variances: list[VarianceRow]
    pvm_bridge: PvmBridge
    management_insights: list[ManagementInsight]
    data_sources: list[DataSource]
    provenance_legend: dict[str, str]
