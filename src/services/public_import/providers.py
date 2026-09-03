from __future__ import annotations
import importlib
import math
from dataclasses import dataclass
from typing import Any, Protocol
from src.models.public_import import Exchange, PublicImportRequest, Venue
from .errors import DependencyMissingError, MalformedUpstreamError, NoDataError, ProviderUnavailableError, UnsupportedExchangeError
from .normalization import canonical_metric, normalize_symbol

@dataclass
class ProviderResult:
    company: dict[str, Any]
    statements: list[dict[str, Any]]
    source_url: str

class PublicFinancialDataProvider(Protocol):
    provider_id: str
    def supports(self, exchange: Exchange, venue: Venue | None = None) -> bool: ...
    def normalize_symbol(self, exchange: Exchange, ticker: str, venue: Venue | None = None) -> str: ...
    def fetch(self, request: PublicImportRequest) -> ProviderResult: ...

class YFinanceProvider:
    provider_id = "yfinance"
    def supports(self, exchange, venue=None): return exchange in {Exchange.US, Exchange.HKEX, Exchange.LSE} and venue is None
    def normalize_symbol(self, exchange, ticker, venue=None): return normalize_symbol(exchange, ticker, venue)
    def fetch(self, request):
        try: yf = importlib.import_module("yfinance")
        except ImportError as exc: raise DependencyMissingError("Install optional public-data-yfinance dependency") from exc
        symbol = self.normalize_symbol(request.exchange, request.ticker, request.venue)
        try:
            t = yf.Ticker(symbol)
            info = getattr(t, "info", {}) or {}
            if not isinstance(info, dict):
                raise MalformedUpstreamError()
            rows: dict[tuple[str, Any], dict[str, Any]] = {}
            frame_specs = (
                ("financials", "annual"), ("quarterly_financials", "quarterly"),
                ("balance_sheet", "annual"), ("quarterly_balance_sheet", "quarterly"),
                ("cashflow", "annual"), ("quarterly_cashflow", "quarterly"),
            )
            for frame_name, period_type in frame_specs:
                frame = getattr(t, frame_name, None)
                if frame is None or not hasattr(frame, "columns"): continue
                for col in frame.columns:
                    period_end = col.date() if hasattr(col, "date") else col
                    row = rows.setdefault((period_type, period_end), {"period_end": period_end, "period_type": period_type, "values": {}})
                    for source_field in frame.index:
                        metric = canonical_metric(source_field)
                        if metric is None:
                            continue
                        try:
                            raw_value = frame.loc[source_field, col]
                            number = None if raw_value is None else float(raw_value)
                        except (TypeError, ValueError, KeyError, AttributeError) as exc:
                            raise MalformedUpstreamError("Provider returned a non-numeric statement value") from exc
                        if number is not None and not math.isfinite(number):
                            continue
                        existing = row["values"].get(metric)
                        if existing is not None and number is not None and existing != number:
                            raise MalformedUpstreamError("Provider returned conflicting statement fields")
                        row["values"][metric] = number
            currency = info.get("currency") or ""
            statements = []
            for row in rows.values():
                if not row["values"]:
                    continue
                # yfinance returns statement values in provider-native units;
                # do not label raw values as millions without conversion.
                statements.append({**row, "currency": currency, "unit_scale": "native", "unit": f"{currency} native units".strip()})
            if not statements: raise NoDataError()
            return ProviderResult({"name": info.get("longName") or info.get("shortName"), "currency": info.get("currency"), "country": info.get("country")}, statements, f"https://finance.yahoo.com/quote/{symbol}")
        except (NoDataError, DependencyMissingError, MalformedUpstreamError): raise
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise MalformedUpstreamError("Provider returned malformed financial data") from exc
        except Exception as exc:
            raise ProviderUnavailableError("Public data provider request failed", details={"retryable": True}) from exc

class AkShareProvider:
    provider_id = "akshare"
    def supports(self, exchange, venue=None): return exchange is Exchange.A_SHARE and venue in {Venue.SSE, Venue.SZSE}
    def normalize_symbol(self, exchange, ticker, venue=None): return normalize_symbol(exchange, ticker, venue)
    def fetch(self, request):
        try: importlib.import_module("akshare")
        except ImportError as exc: raise DependencyMissingError("Install optional public-data-akshare dependency") from exc
        raise ProviderUnavailableError("The approved A-share public-data adapter is not enabled")

class FixtureProvider:
    provider_id = "fixture"
    def __init__(self, fixtures): self.fixtures = fixtures
    def supports(self, exchange, venue=None): return not (exchange is Exchange.A_SHARE and venue is Venue.BSE)
    def normalize_symbol(self, exchange, ticker, venue=None): return normalize_symbol(exchange, ticker, venue)
    def fetch(self, request):
        key = f"{request.exchange.value}:{request.venue.value if request.venue else ''}:{self.normalize_symbol(request.exchange, request.ticker, request.venue)}"
        if key not in self.fixtures: raise NoDataError("No fixture data for ticker")
        return self.fixtures[key]

def default_providers(live_enabled: bool = False):
    return [YFinanceProvider(), AkShareProvider()] if live_enabled else []


def select_provider(request, providers=None):
    for provider in providers or default_providers():
        if provider.supports(request.exchange, request.venue): return provider
    if request.exchange is Exchange.A_SHARE and request.venue is Venue.BSE: raise UnsupportedExchangeError("BSE capability is not approved")
    raise ProviderUnavailableError("Live public-data providers are disabled")
