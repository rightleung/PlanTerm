from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.models.public_import import Exchange, PeriodSelection, PublicImportError, PublicImportPreview, PublicImportRequest, Venue
from src.services.public_import.errors import ProviderTimeoutError


def test_request_contract_requires_explicit_a_share_venue_and_rejects_urls():
    with pytest.raises(ValidationError):
        PublicImportRequest(exchange="A_SHARE", ticker="600519")
    with pytest.raises(ValidationError):
        PublicImportRequest(exchange="US", ticker="https://example.test/AAPL")
    with pytest.raises(ValidationError):
        PublicImportRequest(exchange="US", ticker="AAPL", venue="SSE")


def test_request_contract_serializes_enums_and_periods():
    request = PublicImportRequest(exchange=Exchange.HKEX, ticker="5", periods=PeriodSelection.QUARTERLY)
    assert request.model_dump(mode="json") == {
        "exchange": "HKEX", "ticker": "5", "venue": None, "periods": "quarterly", "include_profile": False,
    }


def test_error_details_are_redaction_safe_by_contract():
    error = PublicImportError(
        error="Timed out",
        error_type="provider_timeout",
        details=ProviderTimeoutError(details={"provider": "fixture", "retryable": True}).details,
    )
    serialized = error.model_dump_json()
    assert "Authorization" not in serialized
    assert "?token=" not in serialized
    assert "stack" not in serialized.lower()


def test_preview_serialization_keeps_iso_dates_and_utc_timestamps():
    request = PublicImportRequest(exchange="US", ticker="AAPL")
    preview = PublicImportPreview(
        preview_id="opaque-preview",
        request={"exchange": request.exchange, "ticker": request.ticker, "venue": None, "normalized_symbol": "AAPL", "periods": request.periods},
        company={"name": "Example", "currency": "USD", "country": "US"},
        statements=[{
            "period_end": date(2024, 12, 31), "period_type": "annual", "fiscal_year": 2024, "fiscal_quarter": None,
            "is_flow": True, "currency": "USD", "unit": "USD millions", "unit_scale": "millions", "values": {"revenue": 1.0},
            "source": {"provider": "fixture", "url": "https://example.test/us/aapl", "retrieved_at": datetime(2025, 1, 2, tzinfo=timezone.utc)},
        }],
        mapping={"dashboard_ready": False, "reason": "native_currency_not_RMB_or_planning_assumptions_missing"},
        disclosures=["Public reported data only; not internal company data."],
        provenance={"provider": "fixture", "source_urls": ["https://example.test/us/aapl"], "retrieved_at": datetime(2025, 1, 2, tzinfo=timezone.utc)},
    )
    body = preview.model_dump(mode="json")
    assert body["statements"][0]["period_end"] == "2024-12-31"
    assert body["statements"][0]["source"]["retrieved_at"] == "2025-01-02T00:00:00Z"
