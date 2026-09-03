from datetime import date, datetime, timezone

import pytest

from src.models.public_import import Exchange, PublicImportRequest, Venue
from src.services.public_import.errors import CurrencyMissingError, InvalidTickerError, MalformedUpstreamError, PeriodInconsistentError
from src.services.public_import.normalization import normalize_statements, normalize_symbol


def statement(period_end="2024-12-31", period_type="annual", **overrides):
    row = {
        "period_end": period_end,
        "period_type": period_type,
        "fiscal_year": 2024,
        "fiscal_quarter": None if period_type == "annual" else 3,
        "is_flow": True,
        "currency": "USD",
        "unit": "USD millions",
        "unit_scale": "millions",
        "values": {"revenue": 10.0, "cash": None},
        "retrieved_at": "2025-01-02T00:00:00Z",
        "as_of": "2024-12-31",
        "filing_date": "2025-01-01",
    }
    row.update(overrides)
    return row


def test_symbol_normalization_is_exchange_and_venue_aware():
    assert normalize_symbol(Exchange.US, "BRK.B") == "BRK-B"
    assert normalize_symbol(Exchange.LSE, "vod.l") == "VOD.L"
    assert normalize_symbol(Exchange.HKEX, "5") == "0005.HK"
    assert normalize_symbol(Exchange.A_SHARE, "600519", Venue.SSE) == "600519.SS"
    assert normalize_symbol(Exchange.A_SHARE, "000001", Venue.SZSE) == "000001.SZ"
    assert normalize_symbol(Exchange.A_SHARE, "430047", Venue.BSE) == "430047.BSE"
    with pytest.raises(InvalidTickerError):
        normalize_symbol(Exchange.US, "AAPL.NYSE")


def test_period_selection_and_iso_metadata_are_normalized():
    request = PublicImportRequest(exchange=Exchange.US, ticker="AAPL", periods="annual")
    rows = normalize_statements([statement(), statement("2024-09-30", "quarterly")], request, "fixture", "https://example.test/us/aapl")
    assert len(rows) == 1
    assert rows[0].period_end == date(2024, 12, 31)
    assert rows[0].fiscal_quarter is None
    assert rows[0].source.as_of == date(2024, 12, 31)


def test_unit_aliases_and_missing_values_are_preserved_without_conversion():
    request = PublicImportRequest(exchange=Exchange.US, ticker="AAPL")
    rows = normalize_statements([statement(unit="USD mn", unit_scale=None)], request, "fixture", "https://example.test/us/aapl")
    assert rows[0].unit_scale == "millions"
    assert rows[0].values["cash"] is None
    assert rows[0].values["revenue"] == 10.0
    assert rows[0].is_flow is False
    assert rows[0].metric_semantics == {"revenue": "flow", "cash": "stock"}


def test_metric_aliases_are_mapped_and_provenance_is_utc():
    request = PublicImportRequest(exchange=Exchange.US, ticker="AAPL")
    rows = normalize_statements([statement(values={"Total Revenue": 10.0, "Cash And Cash Equivalents": 4.0}, retrieved_at="2025-01-02T08:00:00+08:00")], request, "fixture", "https://example.test/us/aapl")
    assert rows[0].values == {"revenue": 10.0, "cash": 4.0}
    assert rows[0].metric_semantics["cash"] == "stock"
    assert rows[0].source.retrieved_at == datetime(2025, 1, 2, tzinfo=timezone.utc)


def test_identical_duplicate_periods_are_deduplicated_but_conflicting_rows_fail():
    request = PublicImportRequest(exchange=Exchange.US, ticker="AAPL")
    duplicate = statement()
    rows = normalize_statements([duplicate, duplicate.copy()], request, "fixture", "https://example.test/us/aapl")
    assert len(rows) == 1
    conflict = statement(values={"revenue": 11.0})
    with pytest.raises(PeriodInconsistentError):
        normalize_statements([duplicate, conflict], request, "fixture", "https://example.test/us/aapl")


def test_currency_and_upstream_shape_errors_are_typed():
    request = PublicImportRequest(exchange=Exchange.US, ticker="AAPL")
    with pytest.raises(CurrencyMissingError):
        normalize_statements([statement(currency="US$")], request, "fixture", "https://example.test/us/aapl")
    with pytest.raises(MalformedUpstreamError):
        normalize_statements([statement(period_end="not-a-date")], request, "fixture", "https://example.test/us/aapl")
    with pytest.raises(MalformedUpstreamError):
        normalize_statements([statement()], request, "fixture", "http://example.test/us/aapl")
    with pytest.raises(MalformedUpstreamError):
        normalize_statements([statement(values={"unapproved_metric": 1.0})], request, "fixture", "https://example.test/us/aapl")


def test_mismatched_fiscal_period_is_typed_as_period_inconsistent():
    request = PublicImportRequest(exchange=Exchange.US, ticker="AAPL")
    with pytest.raises(PeriodInconsistentError):
        normalize_statements([statement(fiscal_year=2023)], request, "fixture", "https://example.test/us/aapl")
