"""Stable, role-based actions for the operating decision view."""
from __future__ import annotations

from decimal import Decimal
from .working_capital_service import dec, json_float
from .csv_input_service import InputError

ACTION_KEYS = {"case_id", "observation", "driver", "impact", "risk", "action", "owner", "due_period", "cadence", "provenance"}


def validate_actions(actions, case_id: str):
    if not isinstance(actions, list):
        raise InputError("validation_error", "actions must be a list")
    if len(actions) > 100:
        raise InputError("validation_error", "At most 100 action rows are allowed")
    validated = []
    for index, item in enumerate(actions, 1):
        if not isinstance(item, dict):
            raise InputError("validation_error", "Action row must be an object", {"row": index})
        missing = sorted(ACTION_KEYS - set(item))
        unknown = sorted(set(item) - ACTION_KEYS)
        if missing:
            raise InputError("validation_error", "Action row is missing required fields", {"row": index, "missing": missing})
        if unknown:
            raise InputError("unexpected_input_key", "Action row has unexpected fields", {"row": index, "fields": unknown})
        if item["case_id"] != case_id:
            raise InputError("invalid_case", "Action row case_id does not match path", {"row": index})
        if item["provenance"] != "synthetic_plan":
            raise InputError("invalid_provenance", "Action input provenance must be synthetic_plan", {"row": index})
        if any(not isinstance(item[field], str) for field in ACTION_KEYS - {"case_id", "impact", "provenance"}):
            raise InputError("validation_error", "Action text fields must be strings", {"row": index})
        if any(len(item[field]) > 2000 for field in ACTION_KEYS - {"case_id", "impact", "provenance"}):
            raise InputError("validation_error", "Action text fields are too long", {"row": index})
        try:
            impact = dec(item["impact"])
        except ValueError as exc:
            raise InputError("invalid_range", "Action impact must be a finite JSON number", {"row": index, "field": "impact"}) from exc
        validated.append({**item, "impact": json_float(impact)})
    return validated


def build_actions(*, case_id: str, cash_bridge=None, forecast_accuracy=None, actions=None):
    if actions is not None:
        validated = validate_actions(actions, case_id)
        # Client action text is accepted as request-scoped data, but derived impact
        # and provenance are always server-owned.
        return [{**item, "impact": None, "input_provenance": item["provenance"], "provenance": "calculated"} for item in validated]
    result = []
    if cash_bridge and cash_bridge.get("headroom") is not None and cash_bridge["headroom"] < 0:
        result.append({"case_id": case_id, "observation": "Illustrative cash headroom is below the minimum buffer", "driver": "cash", "impact": cash_bridge["headroom"], "risk": "Buffer breach", "action": "Review inventory days and CAPEX at the next weekly review", "owner": "Supply Chain Finance", "due_period": "2026-07", "cadence": "weekly", "input_provenance": "calculated", "provenance": "calculated"})
    if forecast_accuracy and forecast_accuracy.get("status") == "eligible" and forecast_accuracy.get("wape", 0) > 0.1:
        result.append({"case_id": case_id, "observation": "Forecast error exceeds the review threshold", "driver": "forecast_accuracy", "impact": forecast_accuracy["wape"], "risk": "Forecast reliability", "action": "Refresh forecast drivers at close+5", "owner": "Group FP&A", "due_period": "2026-07", "cadence": "monthly", "input_provenance": "calculated", "provenance": "calculated"})
    return result
