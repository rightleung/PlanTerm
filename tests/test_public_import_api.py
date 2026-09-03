from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app
from src.config import settings
from src.services.public_import import set_providers
from src.services.public_import.fixtures import fixture_provider
from src.services.public_import.providers import ProviderResult


def setup_module(_module):
    settings.public_import_enabled = True
    settings.public_import_rate_limit_seconds = 0
    set_providers([fixture_provider()])


def test_public_import_preview_is_stateless_and_provenance_backed(tmp_path):
    before = {p: p.stat().st_mtime_ns for p in Path("data/cases/miniso-2026").glob("*")}
    response = TestClient(app).post("/api/v1/public-import/preview", json={"exchange": "US", "ticker": "AAPL"})
    assert response.status_code == 200
    body = response.json()
    assert body["request"]["normalized_symbol"] == "AAPL"
    assert body["provenance"]["provider"] == "fixture"
    assert body["mapping"]["dashboard_ready"] is False
    assert any("not internal company data" in d for d in body["disclosures"])
    assert before == {p: p.stat().st_mtime_ns for p in Path("data/cases/miniso-2026").glob("*")}


def test_exchange_mappings_and_ambiguity():
    client = TestClient(app)
    for payload, symbol in [
        ({"exchange": "LSE", "ticker": "VOD"}, "VOD.L"),
        ({"exchange": "HKEX", "ticker": "5"}, "0005.HK"),
        ({"exchange": "A_SHARE", "venue": "SSE", "ticker": "600519"}, "600519.SS"),
        ({"exchange": "A_SHARE", "venue": "SZSE", "ticker": "000001"}, "000001.SZ"),
    ]:
        response = client.post("/api/v1/public-import/preview", json=payload)
        assert response.status_code == 200
        assert response.json()["request"]["normalized_symbol"] == symbol
    ambiguous = client.post("/api/v1/public-import/preview", json={"exchange": "A_SHARE", "ticker": "600519"})
    assert ambiguous.status_code == 422
    assert ambiguous.json()["error_type"] == "ambiguous_ticker"


def test_bse_is_explicitly_unsupported():
    response = TestClient(app).post("/api/v1/public-import/preview", json={"exchange": "A_SHARE", "venue": "BSE", "ticker": "430047"})
    assert response.status_code == 422
    assert response.json()["error_type"] == "unsupported_exchange"


def test_feature_flag_disables_route():
    settings.public_import_enabled = False
    response = TestClient(app).post("/api/v1/public-import/preview", json={"exchange": "US", "ticker": "AAPL"})
    assert response.status_code == 503
    settings.public_import_enabled = True


def test_validation_errors_are_typed_and_openapi_describes_boundary():
    client = TestClient(app)
    cases = [
        ({"exchange": "NOT_AN_EXCHANGE", "ticker": "AAPL"}, "invalid_exchange"),
        ({"exchange": "US", "venue": "SSE", "ticker": "AAPL"}, "invalid_venue"),
        ({"exchange": "US", "ticker": "https://example.test/AAPL"}, "invalid_ticker"),
        ({"exchange": "US", "ticker": "AAPL", "periods": "monthly"}, "validation_error"),
    ]
    for payload, error_type in cases:
        response = client.post("/api/v1/public-import/preview", json=payload)
        assert response.status_code == 422
        assert response.json()["error_type"] == error_type
    operation = client.get("/openapi.json").json()["paths"]["/api/v1/public-import/preview"]["post"]
    assert "stateless preview" in operation["description"]
    assert "does not create or modify a case" in operation["description"]


def test_no_data_and_malformed_upstream_have_distinct_error_contracts():
    client = TestClient(app)
    missing = client.post("/api/v1/public-import/preview", json={"exchange": "US", "ticker": "NOSUCHFIXTURE"})
    assert missing.status_code == 404
    assert missing.json()["error_type"] == "no_data"

    class MalformedProvider:
        provider_id = "malformed-fixture"

        def supports(self, exchange, venue=None):
            return exchange.value == "US" and venue is None

        def normalize_symbol(self, exchange, ticker, venue=None):
            return ticker.upper()

        def fetch(self, request):
            return ProviderResult({"name": "Malformed", "currency": "USD"}, [{"period_end": "not-a-date", "period_type": "annual", "values": {"revenue": "nan"}}], "https://example.test/malformed")

    set_providers([MalformedProvider()])
    try:
        response = client.post("/api/v1/public-import/preview", json={"exchange": "US", "ticker": "MALFORMED"})
        assert response.status_code == 422
        assert response.json()["error_type"] == "malformed_upstream"
    finally:
        set_providers([fixture_provider()])


def test_dependency_missing_uses_planned_validation_status():
    from src.services.public_import.errors import DependencyMissingError

    class MissingDependencyProvider:
        provider_id = "missing-dependency"

        def supports(self, exchange, venue=None):
            return exchange.value == "US" and venue is None

        def normalize_symbol(self, exchange, ticker, venue=None):
            return ticker.upper()

        def fetch(self, request):
            raise DependencyMissingError("Install the optional provider")

    set_providers([MissingDependencyProvider()])
    try:
        response = TestClient(app).post("/api/v1/public-import/preview", json={"exchange": "US", "ticker": "MISSING"})
        assert response.status_code == 422
        assert response.json()["error_type"] == "dependency_missing"
    finally:
        set_providers([fixture_provider()])


def test_currency_and_period_anomalies_are_typed():
    class AnomalyProvider:
        provider_id = "anomaly-fixture"

        def __init__(self, rows):
            self.rows = rows

        def supports(self, exchange, venue=None):
            return exchange.value == "US" and venue is None

        def normalize_symbol(self, exchange, ticker, venue=None):
            return ticker.upper()

        def fetch(self, request):
            return ProviderResult({"name": "Anomaly", "currency": "USD"}, self.rows, "https://example.test/anomaly")

    client = TestClient(app)
    for rows, error_type, ticker in [
        ([{"period_end": "2024-12-31", "period_type": "annual", "currency": "USD$", "values": {"revenue": 1}}], "currency_missing", "ANOMALY-CURRENCY"),
        ([{"period_end": "2024-12-31", "period_type": "annual", "currency": "USD", "values": {"revenue": 1}}, {"period_end": "2024-12-31", "period_type": "annual", "currency": "USD", "values": {"revenue": 2}}], "period_inconsistent", "ANOMALY-PERIOD"),
    ]:
        set_providers([AnomalyProvider(rows)])
        try:
            response = client.post("/api/v1/public-import/preview", json={"exchange": "US", "ticker": ticker})
            assert response.json()["error_type"] == error_type
        finally:
            set_providers([fixture_provider()])
