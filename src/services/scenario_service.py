"""Scenario orchestration for seed and preview requests."""
from __future__ import annotations
from src.services.csv_input_service import parse_json_rows, expected_keys
from src.services.category_plan_service import calculate_rows

def seed_rows(case):
    return parse_json_rows(list(case.category_seed), case.case_id, case.taxonomy)

def preview(case, rows, selected_variant):
    canonical = parse_json_rows(rows, case.case_id, case.taxonomy)
    return calculate_rows(case, canonical, selected_variant)
