"""Validation helpers shared by case generation and release checks."""

from __future__ import annotations

import math
from collections.abc import Iterable

from src.models.planning import PlanningRecord


REQUIRED_METRICS = {"revenue", "volume", "average_ticket", "cost_of_sales", "gross_profit", "operating_expense", "operating_profit"}


def validate_case_records(records: Iterable[PlanningRecord]) -> None:
    records = tuple(records)
    if not records:
        raise ValueError("Case has no planning records")
    observed = {record.metric for record in records}
    missing = REQUIRED_METRICS - observed
    if missing:
        raise ValueError(f"Case is missing required metrics: {', '.join(sorted(missing))}")
    for record in records:
        if record.value is not None and not math.isfinite(record.value):
            raise ValueError(f"Non-finite value found for {record.metric} in {record.period}")
