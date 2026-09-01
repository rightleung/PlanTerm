"""Planning-input and category scenario contracts."""
from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_serializer
from .planning import PlanVariant, PlanningInputSource


class PlanningInputRow(BaseModel):
    case_id: str
    plan_variant: PlanVariant
    period: str
    business_unit: str
    category_id: str
    volume_change_pct: Decimal
    average_ticket_change_pct: Decimal
    gross_margin_delta_pp: Decimal
    opex_ratio_delta_pp: Decimal


class CanonicalPlanningInputRow(PlanningInputRow):
    category_name: str
    brand: str
    market: str
    provenance: Literal["synthetic_plan"] = "synthetic_plan"

    @field_serializer(
        "volume_change_pct",
        "average_ticket_change_pct",
        "gross_margin_delta_pp",
        "opex_ratio_delta_pp",
        when_used="json",
    )
    def serialize_driver_as_number(self, value: Decimal) -> float:
        """Keep Decimal internally while freezing browser-facing JSON as numbers."""
        return float(value)


class PreviewRequest(BaseModel):
    selected_plan_variant: PlanVariant
    planning_input_source: PlanningInputSource = PlanningInputSource.UPLOAD
    rows: list[PlanningInputRow] = Field(min_length=1)
