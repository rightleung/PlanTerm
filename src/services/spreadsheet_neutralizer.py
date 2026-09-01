"""Type-aware spreadsheet text neutralization shared by export adapters."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

TRIGGER_CHARACTERS = frozenset("=+-@")
TEXT_FIELDS = frozenset({"case_id", "plan_variant", "period", "business_unit", "category_id"})
NUMERIC_FIELDS = frozenset({
    "volume_change_pct",
    "average_ticket_change_pct",
    "gross_margin_delta_pp",
    "opex_ratio_delta_pp",
})


def neutralize_text(value: str) -> str:
    """Prefix one apostrophe for spreadsheet-leading formula characters."""
    if value.startswith("'") or not value or value[0] not in TRIGGER_CHARACTERS:
        return value
    return f"'{value}"


def numeric_text(value: Any, field: str) -> str:
    """Validate numeric-intended values and return a plain decimal string."""
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid numeric value for {field}") from exc
    if not decimal.is_finite():
        raise ValueError(f"Invalid numeric value for {field}")
    return format(decimal, "f")


def sanitize_csv_row(row: dict[str, Any]) -> dict[str, str]:
    """Apply field-aware output rules to one CSV row."""
    output: dict[str, str] = {}
    for field, value in row.items():
        if field in NUMERIC_FIELDS:
            output[field] = numeric_text(value, field)
        elif field in TEXT_FIELDS:
            output[field] = neutralize_text(str(value))
        else:
            output[field] = str(value)
    return output
