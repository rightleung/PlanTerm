"""Read-only listed-company profile lookup shared by the API and UI."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import urlsplit

from src.config import settings
from src.models.public_import import (
    CompanyLookupRequest,
    CompanyLookupResponse,
    CompanyProfile,
    Exchange,
    StatementSource,
    Venue,
)
from src.services.public_import.cache import TTLCache
from src.services.public_import.errors import PublicImportException, ProviderUnavailableError
from src.services.public_import.executor import bounded_call
from src.services.public_import.normalization import normalize_symbol
from src.services.public_import.providers import AkShareProvider, PublicFinancialDataProvider, YFinanceProvider


_profile_cache: TTLCache[CompanyLookupResponse] = TTLCache(
    maxsize=settings.public_import_cache_size,
    ttl=settings.public_import_cache_ttl_seconds,
)
_profile_providers: list[PublicFinancialDataProvider] | None = None


def _safe_website(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        return None
    return candidate


def set_profile_providers(providers: list[PublicFinancialDataProvider] | None) -> None:
    global _profile_providers
    _profile_providers = providers


def infer_market(ticker: str) -> tuple[Exchange, Venue | None]:
    """Infer the common market from a user-entered ticker.

    Explicit exchange/venue fields remain available for ambiguous listings.
    """
    value = ticker.strip().upper()
    if value.endswith(".HK"):
        return Exchange.HKEX, None
    if value.endswith(".L"):
        return Exchange.LSE, None
    if value.endswith(".SS"):
        return Exchange.A_SHARE, Venue.SSE
    if value.endswith(".SH"):
        return Exchange.A_SHARE, Venue.SSE
    if value.endswith(".SZ"):
        return Exchange.A_SHARE, Venue.SZSE
    if value.endswith(".BSE"):
        return Exchange.A_SHARE, Venue.BSE
    if value.isdigit() and len(value) in {4, 5}:
        return Exchange.HKEX, None
    if value.isdigit() and len(value) == 6:
        if value.startswith(("6", "68")):
            return Exchange.A_SHARE, Venue.SSE
        if value.startswith(("0", "2", "3")):
            return Exchange.A_SHARE, Venue.SZSE
        if value.startswith(("4", "8")):
            return Exchange.A_SHARE, Venue.BSE
    return Exchange.US, None


def resolve_lookup(request: CompanyLookupRequest) -> tuple[Exchange, Venue | None, str]:
    exchange, venue = request.exchange, request.venue
    if exchange is None:
        exchange, inferred_venue = infer_market(request.ticker)
        venue = inferred_venue
    if exchange is Exchange.A_SHARE and venue is None:
        raise ProviderUnavailableError("A-share lookup requires an explicit venue")
    return exchange, venue, normalize_symbol(exchange, request.ticker, venue)


def _providers_for(request: CompanyLookupRequest, exchange: Exchange, venue: Venue | None):
    if _profile_providers is not None:
        return _profile_providers
    if request.data_source == "yfinance":
        return [YFinanceProvider()]
    if request.data_source == "akshare":
        return [AkShareProvider()]
    if exchange is Exchange.A_SHARE:
        return [AkShareProvider(), YFinanceProvider()]
    return [YFinanceProvider()]


def _select_profile_providers(request, exchange, venue):
    candidates = []
    for provider in _providers_for(request, exchange, venue):
        if provider.supports(exchange, venue) and hasattr(provider, "fetch_profile"):
            candidates.append(provider)
    if candidates:
        return candidates
    if exchange is Exchange.A_SHARE and venue is Venue.BSE:
        raise PublicImportException("unsupported_exchange", "BSE capability is not approved")
    raise ProviderUnavailableError("No company profile provider is available")


async def lookup_company_profile(request: CompanyLookupRequest) -> CompanyLookupResponse:
    exchange, venue, symbol = resolve_lookup(request)
    key = f"{request.data_source}:{exchange.value}:{venue.value if venue else ''}:{symbol}"
    cached = _profile_cache.get(key)
    if cached is not None:
        return cached
    try:
        last_error: PublicImportException | None = None
        result = None
        provider = None
        for candidate in _select_profile_providers(request, exchange, venue):
            try:
                result = await bounded_call(
                    lambda candidate=candidate: candidate.fetch_profile(request, symbol),
                    timeout=settings.public_import_provider_timeout_seconds,
                )
                provider = candidate
                break
            except PublicImportException as exc:
                last_error = exc
                if request.data_source != "auto" or exc.error_type not in {"dependency_missing", "provider_unavailable"}:
                    raise
        if result is None or provider is None:
            raise last_error or ProviderUnavailableError("Company profile provider is unavailable")
        retrieved_at = datetime.now(timezone.utc)
        profile = CompanyProfile(
            name=str(result.company.get("name") or symbol),
            symbol=symbol,
            exchange=exchange,
            venue=venue,
            currency=str(result.company.get("currency")).strip() if result.company.get("currency") else None,
            country=result.company.get("country"),
            sector=result.company.get("sector"),
            industry=result.company.get("industry"),
            website=_safe_website(result.company.get("website")),
            description=result.company.get("description"),
            employees=result.company.get("employees"),
            market_cap=result.market_cap,
            market_cap_currency=str(result.company.get("currency")).strip() if result.company.get("currency") else None,
        )
        response = CompanyLookupResponse(
            profile=profile,
            source=StatementSource(provider=provider.provider_id, url=result.source_url, retrieved_at=retrieved_at),
            disclosures=[
                "Public company information only; not internal company data.",
                "Provider data may be delayed, restated or incomplete.",
            ],
        )
        _profile_cache.set(key, response)
        return response
    except PublicImportException:
        raise
    except asyncio.TimeoutError as exc:
        raise PublicImportException("provider_timeout", "Company profile provider timed out", {"provider": getattr(provider, "provider_id", None)}) from exc
    except Exception as exc:
        raise ProviderUnavailableError("Company profile provider request failed", {"provider": getattr(provider, "provider_id", None), "retryable": True}) from exc
