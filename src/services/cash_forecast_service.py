"""Illustrative cash bridge calculations."""
from __future__ import annotations
from decimal import Decimal
from .working_capital_service import dec, json_float


def calculate_cash_bridge(row: dict) -> dict:
    op, prior_ar, current_ar = (dec(row.get(key)) for key in ("operating_profit", "prior_ar", "current_ar"))
    prior_inventory, current_inventory = (dec(row.get(key)) for key in ("prior_inventory", "current_inventory"))
    current_ap, prior_ap = (dec(row.get(key)) for key in ("current_ap", "prior_ap"))
    capex, other = dec(row.get("capex")), dec(row.get("other_cash_items"))
    opening, buffer = dec(row.get("opening_cash")), dec(row.get("minimum_cash_buffer"))
    required = (op, prior_ar, current_ar, prior_inventory, current_inventory, current_ap, prior_ap, capex, other, opening, buffer)
    result = {**row, "net_cash_change": None, "closing_illustrative_cash": None, "headroom": None, "cash_identity_residual": None, "status": "not_eligible", "input_provenance": row.get("provenance"), "provenance": "calculated", "cash_label": "illustrative_cash_balance"}
    if all(value is not None for value in required):
        net = op + (prior_ar - current_ar) + (prior_inventory - current_inventory) + (current_ap - prior_ap) - capex + other
        closing = opening + net
        result.update(net_cash_change=json_float(net), closing_illustrative_cash=json_float(closing), headroom=json_float(closing - buffer), cash_identity_residual=json_float(closing - opening - net), status="eligible")
    return result


def forecast_cash(rows):
    return [calculate_cash_bridge(row) for row in rows]
