from __future__ import annotations

import hashlib
import json
import logging
import asyncio
import random
import time
from datetime import datetime, timezone

from src.config import settings
from src.models.public_import import PublicImportCompany, PublicImportMapping, PublicImportPreview, PublicImportProvenance, PublicImportRequest, PublicImportRequestEcho
from .cache import negative_cache, positive_cache, rate_limit_cache
from .errors import PublicImportException, ProviderTimeoutError, ProviderUnavailableError, RateLimitedError
from .executor import bounded_call
from .normalization import normalize_statements
from .providers import default_providers, select_provider
from .rate_limit import enforce

logger = logging.getLogger(__name__)
_providers = None
_flights: dict[str, asyncio.Lock] = {}
_flight_refs: dict[str, int] = {}
_flights_guard = __import__("threading").Lock()

def set_providers(providers):
    global _providers
    _providers = providers

async def preview_public_import(request: PublicImportRequest, *, providers=None, rate_interval: float = 1.0) -> PublicImportPreview:
    active_providers = providers if providers is not None else _providers
    if active_providers is None:
        active_providers = default_providers(settings.public_import_live_enabled)
    provider = select_provider(request, active_providers)
    symbol = provider.normalize_symbol(request.exchange, request.ticker, request.venue)
    key = json.dumps({"exchange": request.exchange.value, "venue": request.venue.value if request.venue else None, "symbol": symbol, "periods": request.periods.value, "provider": provider.provider_id, "profile": request.include_profile}, sort_keys=True)
    correlation_id = hashlib.sha256(key.encode()).hexdigest()[:12]
    logger.info("public_import.request correlation_id=%s exchange=%s symbol=%s provider=%s periods=%s", correlation_id, request.exchange.value, symbol, provider.provider_id, request.periods.value)
    cached = positive_cache.get(key)
    if cached is not None:
        logger.info("public_import.cache_hit provider=%s symbol=%s", provider.provider_id, symbol)
        return cached
    rate_limited = rate_limit_cache.get(key)
    if isinstance(rate_limited, PublicImportException):
        raise rate_limited
    negative = negative_cache.get(key)
    if isinstance(negative, PublicImportException): raise negative
    with _flights_guard:
        flight = _flights.setdefault(key, asyncio.Lock())
        _flight_refs[key] = _flight_refs.get(key, 0) + 1
    try:
        async with flight:
            cached = positive_cache.get(key)
            if cached is not None:
                return cached
            rate_limited = rate_limit_cache.get(key)
            if isinstance(rate_limited, PublicImportException):
                raise rate_limited
            negative = negative_cache.get(key)
            if isinstance(negative, PublicImportException): raise negative
            try:
                return await asyncio.wait_for(
                    _fetch_and_build(request, provider, symbol, key, rate_interval, correlation_id),
                    timeout=settings.public_import_deadline_seconds,
                )
            except asyncio.TimeoutError as exc:
                error = ProviderTimeoutError(details={"provider": provider.provider_id, "retryable": True})
                negative_cache.set(key, error)
                logger.warning("public_import.timeout correlation_id=%s provider=%s symbol=%s", correlation_id, provider.provider_id, symbol)
                raise error from exc
    finally:
        with _flights_guard:
            refs = _flight_refs.get(key, 1) - 1
            if refs <= 0 and _flights.get(key) is flight:
                _flight_refs.pop(key, None)
                _flights.pop(key, None)
            else:
                _flight_refs[key] = refs

async def _fetch_and_build(request, provider, symbol, key, rate_interval, correlation_id):
    logger.info("public_import.cache_miss provider=%s symbol=%s", provider.provider_id, symbol)
    started = time.perf_counter()
    try:
        try:
            enforce(provider.provider_id, rate_interval)
        except RateLimitedError as exc:
            rate_limit_cache.set(key, exc)
            logger.warning("public_import.rate_limited correlation_id=%s provider=%s symbol=%s", correlation_id, provider.provider_id, symbol)
            raise
        last_error: PublicImportException | None = None
        retry_count = 0
        logger.info("public_import.provider_start correlation_id=%s provider=%s symbol=%s", correlation_id, provider.provider_id, symbol)
        for attempt in range(settings.public_import_retry_count + 1):
            try:
                result = await bounded_call(
                    lambda: provider.fetch(request),
                    timeout=settings.public_import_provider_timeout_seconds,
                )
                retry_count = attempt
                break
            except (ProviderTimeoutError, ProviderUnavailableError) as exc:
                last_error = exc
                retry_count = attempt
                if attempt >= settings.public_import_retry_count: raise
                await asyncio.sleep(0.05 * (2 ** attempt) * random.uniform(0.8, 1.2))
        else:
            raise last_error or ProviderUnavailableError()
        statements = normalize_statements(result.statements, request, provider.provider_id, result.source_url, result.company.get("currency"))
        if not statements: raise PublicImportException("no_data", "No statements matched the requested periods")
        retrieved = max((s.source.retrieved_at for s in statements), default=datetime.now(timezone.utc))
        source_urls = sorted({s.source.url for s in statements})
        preview_id = hashlib.sha256(f"{key}|{retrieved.isoformat()}".encode()).hexdigest()[:24]
        preview = PublicImportPreview(
            preview_id=preview_id,
            request=PublicImportRequestEcho(exchange=request.exchange, ticker=request.ticker.strip(), venue=request.venue, normalized_symbol=symbol, periods=request.periods),
            company=PublicImportCompany(**result.company), statements=statements,
            mapping=PublicImportMapping(dashboard_ready=False, reason="native_currency_not_RMB_or_planning_assumptions_missing"),
            disclosures=["Public reported data only; not internal company data.", "Provider data may be delayed, restated or incomplete.", "Native currency and units are preserved; no FX conversion is applied."],
            provenance=PublicImportProvenance(provider=provider.provider_id, source_urls=source_urls, retrieved_at=retrieved, as_of=max((s.source.as_of for s in statements if s.source.as_of), default=None)),
        )
        positive_cache.set(key, preview)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info("public_import.provider_success correlation_id=%s provider=%s symbol=%s duration_ms=%s retry_count=%s statement_count=%s", correlation_id, provider.provider_id, symbol, duration_ms, retry_count, len(statements))
        logger.info("public_import.preview_returned correlation_id=%s provider=%s symbol=%s statements=%d", correlation_id, provider.provider_id, symbol, len(statements))
        return preview
    except PublicImportException as exc:
        if not isinstance(exc, RateLimitedError):
            negative_cache.set(key, exc)
        logger.warning("public_import.provider_error correlation_id=%s provider=%s symbol=%s error_type=%s duration_ms=%s", correlation_id, provider.provider_id, symbol, exc.error_type, round((time.perf_counter() - started) * 1000, 2))
        raise
    except Exception as exc:
        error = ProviderUnavailableError(details={"provider": provider.provider_id, "retryable": True})
        negative_cache.set(key, error)
        logger.warning("public_import.provider_error correlation_id=%s provider=%s symbol=%s error_type=%s", correlation_id, provider.provider_id, symbol, error.error_type)
        raise error from exc
