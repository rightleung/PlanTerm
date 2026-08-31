from fastapi.testclient import TestClient
import pytest

from src.api import app


client = TestClient(app)


def test_health_and_case_list():
    assert client.get("/health").json()["status"] == "ok"
    payload = client.get("/api/v1/cases").json()
    assert payload["cases"][0]["case_id"] == "miniso-2026"


def test_dashboard_default_and_filters():
    response = client.get("/api/v1/cases/miniso-2026/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_filters"] == {"brand": "all", "market": "all"}
    assert len(payload["business_unit_variances"]) == 3
    assert abs(payload["pvm_bridge"]["reconciliation_difference"]) <= 0.01
    assert len(payload["management_insights"]) == 2

    mainland = client.get("/api/v1/cases/miniso-2026/dashboard?brand=MINISO&market=mainland")
    assert mainland.status_code == 200
    assert len(mainland.json()["business_unit_variances"]) == 1
    assert mainland.json()["business_unit_variances"][0]["business_unit"] == "MINISO - Chinese Mainland"

    combinations = payload["available_filters"]["valid_combinations"]
    assert {tuple(item.values()) for item in combinations} == {
        ("MINISO", "mainland", "MINISO - Chinese Mainland"),
        ("MINISO", "overseas", "MINISO - Overseas"),
        ("TOP_TOY", "global", "TOP TOY - Global"),
    }


@pytest.mark.parametrize("brand,market", [
    ("all", "all"), ("all", "mainland"), ("all", "overseas"), ("all", "global"),
    ("MINISO", "all"), ("MINISO", "mainland"), ("MINISO", "overseas"),
    ("TOP_TOY", "all"), ("TOP_TOY", "global"),
])
def test_all_legal_filter_combinations_are_available(brand, market):
    response = client.get(f"/api/v1/cases/miniso-2026/dashboard?brand={brand}&market={market}")
    assert response.status_code == 200


def test_incompatible_filter_combination_returns_structured_422():
    response = client.get("/api/v1/cases/miniso-2026/dashboard?brand=MINISO&market=global")
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_type"] == "incompatible_filters"
    assert payload["details"]["brand"] == "MINISO"
    assert payload["details"]["market"] == "global"
    assert payload["details"]["valid_combinations"]


def test_api_errors_are_normalized_and_safe():
    missing = client.get("/api/v1/cases/does-not-exist/dashboard")
    assert missing.status_code == 404
    assert missing.json()["error_type"] == "case_not_found"
    assert "Traceback" not in missing.text

    invalid = client.get("/api/v1/cases/miniso-2026/dashboard?market=not-a-market")
    assert invalid.status_code == 422
    assert invalid.json()["error_type"] == "validation_error"
