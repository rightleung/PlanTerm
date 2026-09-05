"""Bounded, exchange-aware listed-company symbol search."""

from __future__ import annotations

import importlib
from typing import Any

from src.config import settings
from src.models.public_import import Exchange, SymbolSearchResponse, SymbolSearchResult, Venue
from src.services.public_import.cache import TTLCache
from src.services.public_import.errors import DependencyMissingError, ProviderUnavailableError
from src.services.public_import.executor import bounded_call


_search_cache: TTLCache[SymbolSearchResponse] = TTLCache(
    maxsize=settings.public_import_cache_size,
    ttl=settings.public_import_cache_ttl_seconds,
)
_search_provider = None


def set_symbol_search_provider(provider) -> None:
    global _search_provider
    _search_provider = provider


def _market_from_quote(quote: dict[str, Any]) -> tuple[Exchange, Venue | None] | None:
    symbol = str(quote.get("symbol") or "").strip().upper()
    exchange = str(quote.get("exchange") or quote.get("fullExchangeName") or "").strip().upper()
    if symbol.endswith(".HK") or exchange in {"HKG", "HKSE", "HONG KONG"}:
        return Exchange.HKEX, None
    if symbol.endswith(".L") or exchange in {"LSE", "LONDON", "LSEIOB"}:
        return Exchange.LSE, None
    if symbol.endswith((".SS", ".SH")) or exchange in {"SHH", "SHG", "SSE", "SHANGHAI"}:
        return Exchange.A_SHARE, Venue.SSE
    if symbol.endswith(".SZ") or exchange in {"SHZ", "SZE", "SZSE", "SHENZHEN"}:
        return Exchange.A_SHARE, Venue.SZSE
    if exchange in {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "NASDAQ", "NYSE", "AMEX"}:
        return Exchange.US, None
    if symbol and "." not in symbol and not symbol.isdigit():
        return Exchange.US, None
    return None


class YFinanceSymbolSearchProvider:
    provider_id = "yfinance"

    def search(self, query: str) -> list[dict[str, Any]]:
        try:
            yf = importlib.import_module("yfinance")
        except ImportError as exc:
            raise DependencyMissingError("Install the yfinance dependency") from exc
        try:
            search = yf.Search(query)
            quotes = getattr(search, "quotes", [])
            return quotes if isinstance(quotes, list) else []
        except Exception as exc:
            raise ProviderUnavailableError("Symbol search provider is unavailable", {"provider": self.provider_id, "retryable": True}) from exc


async def search_symbols(
    query: str,
    *,
    exchange: Exchange | None = None,
    venue: Venue | None = None,
    limit: int = 10,
) -> SymbolSearchResponse:
    normalized_query = query.strip()
    if not normalized_query:
        return SymbolSearchResponse(query=query, count=0, results=[])
    key = f"{normalized_query.upper()}:{exchange.value if exchange else 'AUTO'}:{venue.value if venue else ''}:{limit}"
    cached = _search_cache.get(key)
    if cached is not None:
        return cached
    provider = _search_provider or YFinanceSymbolSearchProvider()
    quotes = await bounded_call(
        lambda: provider.search(normalized_query),
        timeout=settings.symbol_search_timeout_seconds,
    )
    results: list[SymbolSearchResult] = []
    seen: set[tuple[str, Exchange, Venue | None]] = set()
    for quote in quotes:
        if not isinstance(quote, dict) or str(quote.get("quoteType") or "").upper() != "EQUITY":
            continue
        market = _market_from_quote(quote)
        if market is None:
            continue
        result_exchange, result_venue = market
        if exchange is not None and result_exchange is not exchange:
            continue
        if venue is not None and result_venue is not venue:
            continue
        symbol = str(quote.get("symbol") or "").strip().upper()
        name = str(quote.get("shortname") or quote.get("longname") or symbol).strip()
        unique = (symbol, result_exchange, result_venue)
        if not symbol or not name or unique in seen:
            continue
        seen.add(unique)
        results.append(SymbolSearchResult(
            symbol=symbol,
            name=name,
            exchange=result_exchange,
            venue=result_venue,
            currency=str(quote.get("currency") or "").upper() or None,
            country=str(quote.get("country") or "").strip() or None,
        ))
        if len(results) >= limit:
            break
    response = SymbolSearchResponse(query=normalized_query, count=len(results), results=results)
    _search_cache.set(key, response)
    return response
