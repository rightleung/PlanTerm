from copy import deepcopy
from hashlib import sha256

from fastapi.testclient import TestClient
import pytest

from src.api import app
from src.repositories.case_repository import CaseRepository
from src.services.headcount_service import _revenue
from tests.test_operating_decision_contract import _preview_payload


client = TestClient(app)


def _get(variant="base"):
    response = client.get("/api/v1/cases/miniso-2026/operating-plan", params={"plan_variant": variant})
    assert response.status_code == 200
    return response.json()["workforce_capacity"]


def _payload(variant="base"):
    payload = _preview_payload()
    payload["selected_plan_variant"] = variant
    payload["headcount_rows"] = [
        dict(row, plan_variant=variant)
        for row in CaseRepository().get_case("miniso-2026").headcount_seed
        if row["plan_variant"] == variant
    ]
    payload["working_capital_rows"] = [dict(row, plan_variant=variant) for row in payload["working_capital_rows"]]
    payload["cash_assumption_rows"] = [dict(row, plan_variant=variant) for row in payload["cash_assumption_rows"]]
    return payload


def test_seed_has_complete_bounded_matrix_and_variant_deltas():
    base, upside, downside = (_get(variant) for variant in ("base", "upside", "downside"))
    assert len(base["headcount_rows"]) == 72
    assert {row["role_group"] for row in base["headcount_rows"]} == {"store operations", "commercial", "supply chain", "finance/support"}
    assert {row["period"] for row in base["headcount_rows"]} == {f"2026-{month:02d}" for month in range(7, 13)}
    assert base["selected_vs_base_delta"] == {key: 0 for key in base["selected_vs_base_delta"]}
    assert upside["selected_vs_base_delta"]["required_fte"] > 0
    assert downside["selected_vs_base_delta"]["required_fte"] < 0
    assert {row["period"] for row in base["locked_rows"]} == {"2026-06"}
    assert base["reconciliation_evidence"]["no_double_counting"] is True
    assert base["rollups"]["portfolio"]["row_count"] == 72
    case = CaseRepository().get_case("miniso-2026")
    for period in (f"2026-{month:02d}" for month in range(7, 13)):
        for business_unit in ("MINISO - Chinese Mainland", "MINISO - Overseas", "TOP TOY - Global"):
            allocated = sum(row["revenue"] for row in base["headcount_rows"] if row["period"] == period and row["business_unit"] == business_unit)
            assert allocated == pytest.approx(float(_revenue(case, "base", period, business_unit)))


def test_preview_preserves_statelessness_and_calculates_workforce_values():
    original = _get()
    payload = _payload()
    payload["headcount_rows"][0]["planned_fte"] = "0"
    response = client.post("/api/v1/cases/miniso-2026/operating-plan/preview", json=payload)
    assert response.status_code == 200
    row = response.json()["workforce_capacity"]["headcount_rows"][0]
    assert row["planned_fte"] == 0
    assert row["loaded_cost"] == 0
    assert row["revenue_per_fte"] is None
    assert row["status"] == "zero_capacity"
    assert _get() == original


def test_preview_rejects_headcount_schema_horizon_variant_and_provenance_tampering():
    cases = []
    missing = _payload(); missing["headcount_rows"][0].pop("provenance"); cases.append((missing, "validation_error"))
    extra = _payload(); extra["headcount_rows"][0]["loaded_cost"] = 1; cases.append((extra, "unexpected_input_key"))
    duplicate = _payload(); duplicate["headcount_rows"].append(deepcopy(duplicate["headcount_rows"][0])); cases.append((duplicate, "duplicate_input_key"))
    locked = _payload(); locked["headcount_rows"][0]["period"] = "2026-06"; cases.append((locked, "unexpected_input_key"))
    wrong_variant = _payload(); wrong_variant["headcount_rows"][0]["plan_variant"] = "upside"; cases.append((wrong_variant, "unexpected_input_key"))
    wrong_provenance = _payload(); wrong_provenance["headcount_rows"][0]["provenance"] = "public_reported"; cases.append((wrong_provenance, "invalid_provenance"))
    wrong_case = _payload(); wrong_case["headcount_rows"][0]["case_id"] = "other"; cases.append((wrong_case, "invalid_input_row"))
    wrong_type = _payload(); wrong_type["headcount_rows"][0]["role_group"] = []; cases.append((wrong_type, "validation_error"))
    for payload, error_type in cases:
        response = client.post("/api/v1/cases/miniso-2026/operating-plan/preview", json=payload)
        assert response.status_code == 422, response.text
        assert response.json()["error_type"] == error_type


def test_preview_rejects_negative_nonfinite_and_huge_headcount_values():
    for field, value in (("planned_fte", "-1"), ("planned_fte", "NaN"), ("monthly_loaded_cost", "Infinity"), ("monthly_loaded_cost", "1e10000")):
        payload = _payload()
        payload["headcount_rows"][0][field] = value
        response = client.post("/api/v1/cases/miniso-2026/operating-plan/preview", json=payload)
        assert response.status_code == 422, response.text
        assert response.json()["error_type"] == "invalid_range"


def test_baseline_headcount_inputs_are_synthetic_and_immutable():
    case = CaseRepository().get_case("miniso-2026")
    assert len(case.headcount_seed) == 216
    assert {row["provenance"] for row in case.headcount_seed} == {"synthetic_plan"}
    for path, expected in (
        ("data/cases/miniso-2026/planning_records.csv", "70ec0f851aa0089cfdf1208329b745c08882ed16dbd64be1ce4ced187a65f30a"),
        ("data/cases/miniso-2026/category_scenario_seed.csv", "7ec49244501d915358d31677725adb739ef2ee96bdfebd3587acf51051772477"),
        ("data/source/miniso_public_actuals.json", "81869e9add4426518689d4a6fe19fc25a09f895caff3353325692a1869f6443a"),
        ("data/cases/miniso-2026/metadata.json", "c9acb182338779e2baf20656b1eb47bb82611dacef74eac009955cdd3052ba16"),
    ):
        assert sha256(open(path, "rb").read()).hexdigest() == expected
