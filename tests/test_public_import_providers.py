import asyncio
import importlib
import json
import time
from datetime import date
from pathlib import Path

import pytest

from src.config import settings
from src.models.public_import import Exchange, PublicImportRequest, Venue
from src.services.public_import.errors import DependencyMissingError, NoDataError, ProviderTimeoutError, ProviderUnavailableError, UnsupportedExchangeError
from src.services.public_import.fixtures import fixture_provider
from src.services.public_import.normalization import normalize_symbol
from src.services.public_import.providers import AkShareProvider, ProviderResult, YFinanceProvider, default_providers, select_provider
from src.services.public_import.service import preview_public_import
from src.services.symbol_search_service import _market_from_quote, search_symbols, set_symbol_search_provider


def test_normalization_contract():
    assert normalize_symbol(Exchange.US, "BRK.B") == "BRK-B"
    assert normalize_symbol(Exchange.HKEX, "0005") == "0005.HK"
    assert normalize_symbol(Exchange.LSE, "VOD") == "VOD.L"
    assert normalize_symbol(Exchange.A_SHARE, "600519", Venue.SSE) == "600519.SS"
    assert normalize_symbol(Exchange.A_SHARE, "000001", Venue.SZSE) == "000001.SZ"


def test_fixture_provider_has_annual_and_quarterly_rows():
    provider = fixture_provider()
    result = provider.fetch(PublicImportRequest(exchange=Exchange.US, ticker="AAPL"))
    assert {row["period_type"] for row in result.statements} == {"annual", "quarterly"}
    assert result.company["country"] == "US"
    assert all(row["filing_date"] for row in result.statements)


def test_fixture_inventory_has_native_currency_scale_and_provenance_metadata():
    fixture_dir = Path(__file__).parent / "fixtures" / "public_import"
    expected = {"lse_vod.json", "hkex_0005.json", "us_aapl.json", "sse_600519.json", "szse_000001.json"}
    for name in expected:
        payload = json.loads((fixture_dir / name).read_text())
        assert payload["source_url"].startswith("https://")
        assert payload["unit_scale"] in {"native", "thousands", "millions"}
        assert payload["retrieved_at"].endswith("Z")
        assert {row["period_type"] for row in payload["statements"]} == {"annual", "quarterly"}
        assert all("as_of" in row and "filing_date" in row for row in payload["statements"])


def test_fixture_routing_covers_lse_hkex_sse_and_szse_and_rejects_bse():
    provider = fixture_provider()
    for request in [
        PublicImportRequest(exchange=Exchange.LSE, ticker="VOD"),
        PublicImportRequest(exchange=Exchange.HKEX, ticker="5"),
        PublicImportRequest(exchange=Exchange.A_SHARE, venue=Venue.SSE, ticker="600519"),
        PublicImportRequest(exchange=Exchange.A_SHARE, venue=Venue.SZSE, ticker="000001"),
    ]:
        assert provider.fetch(request).company["currency"]
    request = PublicImportRequest(exchange=Exchange.A_SHARE, venue=Venue.BSE, ticker="430047")
    with pytest.raises(UnsupportedExchangeError):
        select_provider(request, [provider])


def test_live_provider_defaults_are_off_and_optional_dependency_is_lazy(monkeypatch):
    assert default_providers(False) == []
    request = PublicImportRequest(exchange=Exchange.US, ticker="AAPL")
    real_import = importlib.import_module

    def missing(name):
        if name == "yfinance":
            raise ImportError(name)
        return real_import(name)

    from src.services.public_import import providers as provider_module
    monkeypatch.setattr(provider_module.importlib, "import_module", missing)
    with pytest.raises(DependencyMissingError):
        YFinanceProvider().fetch(request)

    # A-share venue routing remains explicit even when the optional module exists.
    monkeypatch.setattr(provider_module.importlib, "import_module", lambda _name: object())
    with pytest.raises(ProviderUnavailableError):
        AkShareProvider().fetch(PublicImportRequest(exchange=Exchange.A_SHARE, venue=Venue.SSE, ticker="600519"))


def test_yfinance_provider_maps_common_fields_and_preserves_native_scale(monkeypatch):
    class Locator:
        def __init__(self, values):
            self.values = values

        def __getitem__(self, key):
            return self.values[key]

    class Frame:
        def __init__(self, values):
            self.index = list(values)
            self.columns = [date(2024, 12, 31)]
            self.loc = Locator({(field, self.columns[0]): value for field, value in values.items()})

    annual_income = Frame({"Total Revenue": 100.0, "Gross Profit": 40.0, "Operating Income": 12.0})
    annual_balance = Frame({"Cash And Cash Equivalents": 25.0, "Total Assets": 80.0, "Total Liabilities": 30.0})
    annual_cashflow = Frame({"Operating Cash Flow": 18.0})

    class Ticker:
        def __init__(self, _symbol):
            pass

        info = {"longName": "Example Co", "currency": "USD", "country": "US"}
        financials = annual_income
        quarterly_financials = None
        balance_sheet = annual_balance
        quarterly_balance_sheet = None
        cashflow = annual_cashflow
        quarterly_cashflow = None

    YFinance = type("YFinance", (), {"Ticker": Ticker})

    from src.services.public_import import providers as provider_module
    monkeypatch.setattr(provider_module.importlib, "import_module", lambda name: YFinance() if name == "yfinance" else importlib.import_module(name))
    result = YFinanceProvider().fetch(PublicImportRequest(exchange=Exchange.US, ticker="AAPL"))
    assert result.statements[0]["values"] == {
        "revenue": 100.0, "gross_profit": 40.0, "operating_profit": 12.0,
        "cash": 25.0, "total_assets": 80.0, "total_liabilities": 30.0, "operating_cf": 18.0,
    }
    assert result.statements[0]["unit_scale"] == "native"


class RetryProvider:
    provider_id = "retry-fixture"

    def __init__(self):
        self.calls = 0

    def supports(self, exchange, venue=None):
        return exchange is Exchange.US and venue is None

    def normalize_symbol(self, exchange, ticker, venue=None):
        return normalize_symbol(exchange, ticker, venue)

    def fetch(self, request):
        self.calls += 1
        if self.calls == 1:
            raise ProviderUnavailableError("temporary outage")
        return ProviderResult(
            {"name": "Retry Fixture", "currency": "USD", "country": "US"},
            [{"period_end": "2024-12-31", "period_type": "annual", "currency": "USD", "unit_scale": "millions", "values": {"revenue": 1.0}}],
            "https://example.test/retry/AAPL",
        )


def test_retry_is_bounded_and_success_is_provenanced(monkeypatch):
    provider = RetryProvider()
    monkeypatch.setattr(settings, "public_import_retry_count", 1)
    preview = asyncio.run(preview_public_import(PublicImportRequest(exchange=Exchange.US, ticker="RETRY"), providers=[provider], rate_interval=0))
    assert provider.calls == 2
    assert preview.provenance.provider == "retry-fixture"
    assert preview.statements[0].values["revenue"] == 1.0


class SlowProvider(RetryProvider):
    provider_id = "timeout-fixture"

    def fetch(self, request):
        time.sleep(0.05)
        return super().fetch(request)


def test_provider_timeout_is_typed(monkeypatch):
    monkeypatch.setattr(settings, "public_import_retry_count", 0)
    monkeypatch.setattr(settings, "public_import_provider_timeout_seconds", 0.01)
    with pytest.raises(ProviderTimeoutError):
        asyncio.run(preview_public_import(PublicImportRequest(exchange=Exchange.US, ticker="SLOW"), providers=[SlowProvider()], rate_interval=0))


def test_unsupported_ticker_is_no_data_without_unrelated_fallback():
    with pytest.raises(NoDataError):
        fixture_provider().fetch(PublicImportRequest(exchange=Exchange.US, ticker="UNRELATED"))


def test_symbol_search_returns_market_metadata_and_filters_lse():
    class SearchProvider:
        def search(self, _query):
            return [
                {"symbol": "VOD.L", "shortname": "Vodafone Group", "quoteType": "EQUITY", "exchange": "LSE", "currency": "GBP"},
                {"symbol": "VOD", "shortname": "Vodafone US", "quoteType": "EQUITY", "exchange": "NMS", "currency": "USD"},
                {"symbol": "VOD.L", "shortname": "Duplicate", "quoteType": "EQUITY", "exchange": "LSE"},
                {"symbol": "VOD", "shortname": "Fund", "quoteType": "ETF", "exchange": "NMS"},
            ]

    set_symbol_search_provider(SearchProvider())
    try:
        result = asyncio.run(search_symbols("vod", exchange=Exchange.LSE, limit=10))
        assert result.count == 1
        assert result.results[0].symbol == "VOD.L"
        assert result.results[0].exchange is Exchange.LSE
        assert result.results[0].currency == "GBP"
    finally:
        set_symbol_search_provider(None)


def test_symbol_search_recognizes_hk_and_a_share_venues():
    assert _market_from_quote({"symbol": "0700.HK", "quoteType": "EQUITY"}) == (Exchange.HKEX, None)
    assert _market_from_quote({"symbol": "600519.SS", "quoteType": "EQUITY"}) == (Exchange.A_SHARE, Venue.SSE)
    assert _market_from_quote({"symbol": "000001.SZ", "quoteType": "EQUITY"}) == (Exchange.A_SHARE, Venue.SZSE)
