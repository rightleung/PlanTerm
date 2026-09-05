from src.models.public_import import CompanyLookupRequest, Exchange, Venue
from src.services.company_profile_service import infer_market, resolve_lookup


def test_infer_market_supports_common_ticker_formats():
    assert infer_market("AAPL") == (Exchange.US, None)
    assert infer_market("0700.HK") == (Exchange.HKEX, None)
    assert infer_market("VOD.L") == (Exchange.LSE, None)
    assert infer_market("600519") == (Exchange.A_SHARE, Venue.SSE)
    assert infer_market("000001") == (Exchange.A_SHARE, Venue.SZSE)


def test_resolve_lookup_preserves_explicit_market_information():
    exchange, venue, symbol = resolve_lookup(CompanyLookupRequest(ticker="5", exchange=Exchange.HKEX))
    assert (exchange, venue, symbol) == (Exchange.HKEX, None, "0005.HK")


def test_a_share_lookup_requires_a_venue_when_explicitly_selected():
    try:
        CompanyLookupRequest(ticker="600519", exchange=Exchange.A_SHARE)
    except ValueError as exc:
        assert "venue" in str(exc).lower()
    else:
        raise AssertionError("expected explicit A-share venue validation")


def test_infer_market_rejects_bse_as_an_explicitly_unsupported_listing_later():
    assert infer_market("430047") == (Exchange.A_SHARE, Venue.BSE)
