"""Working-capital calculations for synthetic operating plans."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from typing import Iterable

TOLERANCE = Decimal("0.01")
DAYS = Decimal("365")


class WorkingCapitalError(ValueError):
    pass


def dec(value, *, nullable: bool = True) -> Decimal | None:
    if value is None or value == "":
        return None if nullable else Decimal(0)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise WorkingCapitalError("Invalid financial value")
    if not result.is_finite():
        raise WorkingCapitalError("Financial values must be finite")
    try:
        if not math.isfinite(float(result)):
            raise WorkingCapitalError("Financial values exceed JSON numeric range")
    except (OverflowError, ValueError):
        raise WorkingCapitalError("Financial values exceed JSON numeric range")
    return result


def json_float(value: Decimal | None) -> float | None:
    """Convert a Decimal only when its JSON representation is finite."""
    if value is None:
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise WorkingCapitalError("Financial values exceed JSON numeric range") from exc
    if not math.isfinite(result):
        raise WorkingCapitalError("Financial values exceed JSON numeric range")
    return result


def calculate_working_capital(row: dict, days_in_period: Decimal = DAYS) -> dict:
    """Calculate balances, CCC and NWC from one assumption row.

    Missing required inputs remain null and receive ``not_eligible`` status.
    """
    revenue = dec(row.get("revenue"))
    cogs = dec(row.get("cogs", row.get("cost_of_sales")))
    ar_days = dec(row.get("ar_days"))
    inventory_days = dec(row.get("inventory_days"))
    ap_days = dec(row.get("ap_days"))
    eligible = all(value is not None for value in (revenue, cogs, ar_days, inventory_days, ap_days))
    values = {"ar_balance": None, "inventory_balance": None, "ap_balance": None, "ccc": None, "nwc": None}
    if eligible:
        values.update(
            ar_balance=revenue * ar_days / days_in_period,
            inventory_balance=cogs * inventory_days / days_in_period,
            ap_balance=cogs * ap_days / days_in_period,
        )
        values["ccc"] = ar_days + inventory_days - ap_days
        values["nwc"] = values["ar_balance"] + values["inventory_balance"] - values["ap_balance"]
    normalized = dict(row)
    for key in ("revenue", "cogs", "cost_of_sales", "ar_days", "inventory_days", "ap_days"):
        if key in normalized:
            value = dec(normalized.get(key))
            normalized[key] = float(value) if value is not None else None
    input_provenance = row.get("provenance")
    return {**normalized, **{key: json_float(value) for key, value in values.items()}, "status": "eligible" if eligible else "not_eligible", "input_provenance": input_provenance, "provenance": "calculated"}


def calculate_rows(rows: Iterable[dict]) -> list[dict]:
    return [calculate_working_capital(row) for row in rows]


def rollup(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    eligible = [row for row in rows if row.get("status") == "eligible"]
    if not eligible:
        return {"ar_balance": None, "inventory_balance": None, "ap_balance": None, "ccc": None, "nwc": None, "status": "not_eligible", "provenance": "calculated"}
    sums = {key: sum((dec(row.get(key), nullable=False) for row in eligible), Decimal(0)) for key in ("ar_balance", "inventory_balance", "ap_balance", "nwc")}
    days = {key: [dec(row.get(key)) for row in eligible] for key in ("ar_days", "inventory_days", "ap_days")}
    result = {**{key: json_float(value) for key, value in sums.items()}, "ccc": None, "status": "eligible", "input_provenance": sorted({row.get("provenance") for row in eligible}), "provenance": "calculated"}
    if all(all(value is not None for value in values) for values in days.values()):
        result["ccc"] = json_float(sum(days["ar_days"], Decimal(0)) + sum(days["inventory_days"], Decimal(0)) - sum(days["ap_days"], Decimal(0)))
    return result
