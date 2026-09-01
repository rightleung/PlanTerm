"""Contracts for the v0.3 operating-decision view.

The models intentionally keep input assumptions separate from calculated output.  All
financial values are recalculated by the service layer with :class:`Decimal`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .planning import PlanVariant, PlanningInputSource


class OperatingRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    plan_variant: PlanVariant
    period: str
    business_unit: str
    ar_days: Decimal | None
    inventory_days: Decimal | None
    ap_days: Decimal | None
    provenance: Literal["synthetic_plan", "calculated"]
    input_provenance: Literal["synthetic_plan", "calculated"] | None = None


class CashAssumptionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    plan_variant: PlanVariant
    period: str
    opening_cash: Decimal | None
    minimum_cash_buffer: Decimal | None
    capex: Decimal | None
    other_cash_items: Decimal | None
    provenance: Literal["synthetic_plan", "calculated"]
    input_provenance: Literal["synthetic_plan", "calculated"] | None = None


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    observation: str
    driver: str
    impact: Decimal | None
    risk: str
    action: str
    owner: str
    due_period: str
    cadence: str
    input_provenance: Literal["synthetic_plan", "calculated"] | None = None
    provenance: Literal["synthetic_plan", "calculated"]


class OperatingPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    selected_plan_variant: PlanVariant
    planning_input_source: PlanningInputSource
    rows: list[dict[str, Any]] = Field(min_length=1)
    working_capital_rows: list[dict[str, Any]] = Field(min_length=1)
    cash_assumption_rows: list[dict[str, Any]] = Field(min_length=1)
    actions: list[dict[str, Any]] = Field(default_factory=list)


# Public names used by the v0.3 service contract.
WCInput = OperatingRow


class CashBridgeRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str
    plan_variant: PlanVariant
    net_cash_change: Decimal | None = None
    closing_illustrative_cash: Decimal | None = None
    headroom: Decimal | None = None
    status: str = "not_eligible"
    provenance: Literal["calculated"] = "calculated"


class ForecastAccuracy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wape: Decimal | None = None
    bias: Decimal | None = None
    directional_hit_rate: Decimal | None = None
    eligible_periods: int = 0
    status: str = "not_eligible"
    provenance: Literal["calculated"] = "calculated"


class ForecastSnapshot(BaseModel):
    case_id: str
    period: str
    business_unit: str
    metric: str
    actual: Decimal | None = None
    forecast: Decimal | None = None
    provenance: Literal["synthetic_plan", "calculated"]
