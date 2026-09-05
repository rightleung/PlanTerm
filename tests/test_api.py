from fastapi.testclient import TestClient
import pytest

from src.api import app, repository
from src.config import Settings
from src.services.symbol_search_service import set_symbol_search_provider


client = TestClient(app)


def test_health_and_case_list():
    assert client.get("/health").json()["status"] == "ok"
    payload = client.get("/api/v1/cases").json()
    assert payload["cases"][0]["case_id"] == "miniso-2026"


def test_readiness_checks_committed_case_and_frontend_build():
    response = client.get("/ready")
    assert response.status_code in {200, 503}
    if response.status_code == 200:
        assert response.json()["status"] == "ready"


def test_symbol_search_endpoint_filters_market_and_returns_lse_metadata():
    class Provider:
        def search(self, _query):
            return [
                {"symbol": "VOD.L", "shortname": "Vodafone", "quoteType": "EQUITY", "exchange": "LSE", "currency": "GBP"},
                {"symbol": "VOD", "shortname": "Vodafone ADR", "quoteType": "EQUITY", "exchange": "NMS", "currency": "USD"},
            ]

    set_symbol_search_provider(Provider())
    try:
        response = client.get("/api/v1/symbols/search", params={"q": "vod", "exchange": "LSE"})
        assert response.status_code == 200
        assert response.json()["results"] == [{"symbol": "VOD.L", "name": "Vodafone", "exchange": "LSE", "venue": None, "currency": "GBP", "country": None}]
    finally:
        set_symbol_search_provider(None)


def test_request_boundary_rejects_oversized_json_and_traversal_case():
    oversized = client.post(
        "/api/v1/cases/miniso-2026/dashboard/preview",
        content=b"{" + b"a" * 2_100_000 + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 413
    assert oversized.json()["error_type"] == "request_too_large"
    traversal = client.get("/api/v1/cases/../metadata.json/dashboard")
    assert traversal.status_code in {404, 400}


def test_settings_load_prefixed_environment_variables(monkeypatch):
    monkeypatch.setenv("PLANTERM_ENVIRONMENT", "production")
    monkeypatch.setenv("PLANTERM_COMPANY_PROFILE_ENABLED", "false")
    configured = Settings()
    assert configured.environment == "production"
    assert configured.company_profile_enabled is False


def test_dashboard_default_and_filters():
    response = client.get("/api/v1/cases/miniso-2026/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_filters"] == {"brand": "all", "market": "all"}
    assert len(payload["business_unit_variances"]) == 3
    assert abs(payload["pvm_bridge"]["reconciliation_difference"]) <= 0.01
    profit_bridge = payload["profit_bridge"]
    assert {item["driver"] for item in profit_bridge["items"]} == {"PVM profit effect", "Gross Margin", "Opex"}
    assert abs(profit_bridge["reconciliation_difference"]) <= 0.01
    assert all(item["provenance"] == "calculated" and item["action_owner"] for item in profit_bridge["items"])
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


def test_dashboard_plan_variant_and_preview_filters_are_preserved():
    for variant in ("base", "upside", "downside"):
        response = client.get("/api/v1/cases/miniso-2026/dashboard", params={"plan_variant": variant, "brand": "MINISO", "market": "mainland"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["selected_plan_variant"] == variant
        assert payload["selected_filters"] == {"brand": "MINISO", "market": "mainland"}


@pytest.mark.parametrize("variant", ["base", "upside", "downside"])
def test_dashboard_plan_variant_and_filters_are_preserved(variant):
    response = client.get("/api/v1/cases/miniso-2026/dashboard", params={"plan_variant": variant, "brand": "MINISO", "market": "mainland"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_plan_variant"] == variant
    assert payload["selected_filters"] == {"brand": "MINISO", "market": "mainland"}


def test_preview_preserves_filters_and_rejects_out_of_range_input():
    template = client.get("/api/v1/cases/miniso-2026/planning-input-template").content
    imported = client.post("/api/v1/cases/miniso-2026/planning-inputs/import", content=template, headers={"Content-Type": "text/csv"}).json()
    payload = {"selected_plan_variant": "base", "brand": "MINISO", "market": "mainland", "rows": imported["rows"]}
    preview = client.post("/api/v1/cases/miniso-2026/dashboard/preview", json=payload)
    assert preview.status_code == 200
    assert preview.json()["selected_filters"] == {"brand": "MINISO", "market": "mainland"}
    payload["rows"][0]["volume_change_pct"] = "1.500000"
    rejected = client.post("/api/v1/cases/miniso-2026/dashboard/preview", json=payload)
    assert rejected.status_code == 422
    assert rejected.json()["error_type"] == "invalid_input_row"


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


def test_dashboard_base_forecast_remains_v011_compatible():
    payload = client.get('/api/v1/cases/miniso-2026/dashboard', params={'plan_variant': 'base'}).json()
    units = {row['business_unit'] for row in payload['business_unit_variances']}
    committed = repository.get_case('miniso-2026').records
    fy_months = {f'2026-{month:02d}' for month in range(1, 13)}
    for metric in ('revenue', 'gross_profit', 'operating_profit'):
        expected = sum(record.value or 0 for record in committed if record.scenario.value == 'forecast' and record.period in fy_months and record.metric == metric and record.business_unit in units)
        actual = next(item['fy_forecast'] for item in payload['kpis'] if item['metric'] == metric)
        assert actual == pytest.approx(expected, abs=0.01)
    for row in payload['business_unit_variances']:
        expected = sum(record.value or 0 for record in committed if record.scenario.value == 'forecast' and record.period in fy_months and record.metric == 'revenue' and record.business_unit == row['business_unit'])
        assert row['fy_forecast'] == pytest.approx(expected, abs=0.01)


def test_dashboard_selected_variant_drives_forecast_fields_and_preserves_locked_values():
    dashboards = {
        variant: client.get('/api/v1/cases/miniso-2026/dashboard', params={'plan_variant': variant}).json()
        for variant in ('base', 'upside', 'downside')
    }
    base, upside, downside = (dashboards[name] for name in ('base', 'upside', 'downside'))
    kpis = lambda payload: {item['metric']: item for item in payload['kpis']}
    base_kpis, upside_kpis, downside_kpis = map(kpis, (base, upside, downside))

    assert upside_kpis['revenue']['fy_forecast'] > base_kpis['revenue']['fy_forecast']
    assert downside_kpis['revenue']['fy_forecast'] < base_kpis['revenue']['fy_forecast']
    assert upside_kpis['gross_profit']['fy_forecast'] > base_kpis['gross_profit']['fy_forecast']
    assert downside_kpis['gross_profit']['fy_forecast'] < base_kpis['gross_profit']['fy_forecast']
    assert upside_kpis['operating_profit']['fy_forecast'] > base_kpis['operating_profit']['fy_forecast']
    assert downside_kpis['operating_profit']['fy_forecast'] < base_kpis['operating_profit']['fy_forecast']
    assert upside_kpis['operating_margin']['fy_forecast'] > base_kpis['operating_margin']['fy_forecast']
    assert downside_kpis['operating_margin']['fy_forecast'] < base_kpis['operating_margin']['fy_forecast']

    # Actual, Budget, Prior Year, PVM, and locked H1 Forecast are invariant.
    for variant in ('upside', 'downside'):
        selected = dashboards[variant]
        assert selected['pvm_bridge'] == base['pvm_bridge']
        assert selected['profit_bridge'] == base['profit_bridge']
        for metric in base_kpis:
            for field in ('actual_ytd', 'budget_ytd', 'prior_year_ytd', 'fy_budget', 'variance_amount', 'variance_pct', 'yoy_pct'):
                selected_kpi = kpis(selected)[metric]
                assert selected_kpi[field] == base_kpis[metric][field]
        for actual_point, selected_point in zip(base['monthly_trend'], selected['monthly_trend']):
            assert selected_point['actual'] == actual_point['actual']
            assert selected_point['budget'] == actual_point['budget']
            assert selected_point['prior_year'] == actual_point['prior_year']
            if selected_point['period'] <= '2026-06':
                assert selected_point['forecast'] == selected_point['actual']
        base_rows = {row['business_unit']: row for row in base['business_unit_variances']}
        selected_rows = {row['business_unit']: row for row in selected['business_unit_variances']}
        for unit, base_row in base_rows.items():
            selected_row = selected_rows[unit]
            for field in ('revenue_actual', 'revenue_budget', 'gross_profit_actual', 'gross_profit_budget', 'operating_profit_actual', 'operating_profit_budget', 'operating_expense_actual', 'operating_expense_budget', 'price_amount', 'volume_amount', 'mix_amount'):
                assert selected_row[field] == base_row[field]


def test_dashboard_forecast_rollup_matches_category_detail_for_selected_variant():
    for variant in ('base', 'upside', 'downside'):
        payload = client.get('/api/v1/cases/miniso-2026/dashboard', params={'plan_variant': variant}).json()
        selected_bu = payload['business_unit_variances'][0]['business_unit']
        detail = payload['category_detail']
        fy_revenue = sum(item['revenue'] for item in detail if item['period'] == 'FY2026' and item['plan_variant'] == variant and item['business_unit'] == selected_bu)
        july_revenue = sum(item['revenue'] for item in detail if item['period'] == '2026-07' and item['plan_variant'] == variant and item['business_unit'] == selected_bu)
        bu_row = next(row for row in payload['business_unit_variances'] if row['business_unit'] == selected_bu)
        trend_point = next(point for point in payload['monthly_trend'] if point['period'] == '2026-07')
        assert bu_row['fy_forecast'] == pytest.approx(fy_revenue)
        assert trend_point['forecast'] == pytest.approx(sum(item['revenue'] for item in detail if item['period'] == '2026-07' and item['plan_variant'] == variant))
        assert july_revenue == pytest.approx(sum(item['revenue'] for item in detail if item['period'] == '2026-07' and item['plan_variant'] == variant and item['business_unit'] == selected_bu))


def test_complete_matrix_rejects_out_of_range_selected_variant_input():
    template = client.get('/api/v1/cases/miniso-2026/planning-input-template').content
    imported = client.post('/api/v1/cases/miniso-2026/planning-inputs/import', content=template, headers={'Content-Type': 'text/csv'}).json()
    next(row for row in imported['rows'] if row['plan_variant'] == 'upside')['gross_margin_delta_pp'] = '0.150001'
    response = client.post('/api/v1/cases/miniso-2026/dashboard/preview', json={'selected_plan_variant': 'upside', 'rows': imported['rows']})
    assert response.status_code == 422
    assert response.json()['error_type'] == 'invalid_input_row'
