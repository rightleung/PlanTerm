from fastapi.testclient import TestClient

from src.api import app
from src.repositories.case_repository import CaseRepository
from src.services.scenario_service import seed_rows


client = TestClient(app)


def test_operating_plan_contract_and_variant_sensitivity():
    base = client.get("/api/v1/cases/miniso-2026/operating-plan").json()
    upside = client.get("/api/v1/cases/miniso-2026/operating-plan", params={"plan_variant": "upside"}).json()
    assert set(("as_of_date", "planning_horizon", "plan_variant", "provenance_legend", "working_capital", "cash_bridge", "forecast_accuracy", "actions", "decision_table", "reconciliation")) <= set(base)
    assert base["cash_bridge"]["disclosure"].startswith("Illustrative")
    assert base["reconciliation"]["status"] == "reconciled"
    assert base["decision_table"][0]["fy_operating_profit_delta"] == 0
    assert upside["plan_variant"] == "upside"


def test_operating_plan_invalid_case_and_variant():
    assert client.get("/api/v1/cases/missing/operating-plan").status_code == 404
    assert client.get("/api/v1/cases/miniso-2026/operating-plan", params={"plan_variant": "other"}).status_code == 422


def _preview_payload():
    case = CaseRepository().get_case("miniso-2026")
    rows = [row.model_dump(mode="json") for row in seed_rows(case)]
    wc = [dict(row) for row in case.working_capital_seed if row["plan_variant"] == "base"]
    cash = [dict(row, opening_cash=case.cash_assumptions["opening_cash"], minimum_cash_buffer=case.cash_assumptions["minimum_cash_buffer"]) for row in case.cash_assumptions["rows"] if row["plan_variant"] == "base"]
    return {"case_id": case.case_id, "selected_plan_variant": "base", "planning_input_source": "editor", "rows": rows, "working_capital_rows": wc, "cash_assumption_rows": cash}


def test_preview_rejects_null_missing_extra_and_non_object_rows():
    payload = _preview_payload()
    for rows in ([None] + payload["working_capital_rows"][1:], payload["working_capital_rows"][1:], [dict(payload["working_capital_rows"][0], extra=1)] + payload["working_capital_rows"][1:]):
        bad = dict(payload, working_capital_rows=rows)
        response = client.post("/api/v1/cases/miniso-2026/operating-plan/preview", json=bad)
        assert response.status_code == 422
        assert response.json()["error_type"] in {"validation_error", "unexpected_input_key", "incomplete_input_matrix", "invalid_input_row"}


def test_preview_rejects_huge_decimal_and_malformed_action():
    payload = _preview_payload()
    huge = dict(payload["working_capital_rows"][0], ar_days="1e10000")
    response = client.post("/api/v1/cases/miniso-2026/operating-plan/preview", json=dict(payload, working_capital_rows=[huge] + payload["working_capital_rows"][1:]))
    assert response.status_code == 422
    assert response.json()["error_type"] == "invalid_range"
    malformed = dict(payload, actions=[{"case_id": "miniso-2026"}])
    response = client.post("/api/v1/cases/miniso-2026/operating-plan/preview", json=malformed)
    assert response.status_code == 422
    assert response.json()["error_type"] == "validation_error"
