from __future__ import annotations
import importlib
import math
from dataclasses import dataclass
from typing import Any, Protocol
from src.models.public_import import CompanyLookupRequest, Exchange, PublicImportRequest, Venue
from .errors import DependencyMissingError, MalformedUpstreamError, NoDataError, ProviderUnavailableError, UnsupportedExchangeError
from .normalization import canonical_metric, normalize_symbol

@dataclass
class ProviderResult:
    company: dict[str, Any]
    statements: list[dict[str, Any]]
    source_url: str


@dataclass
class ProfileResult:
    company: dict[str, Any]
    market_cap: float | None
    source_url: str

class PublicFinancialDataProvider(Protocol):
    provider_id: str
    def supports(self, exchange: Exchange, venue: Venue | None = None) -> bool: ...
    def normalize_symbol(self, exchange: Exchange, ticker: str, venue: Venue | None = None) -> str: ...
    def fetch(self, request: PublicImportRequest) -> ProviderResult: ...
    def fetch_profile(self, request: CompanyLookupRequest, symbol: str) -> ProfileResult: ...

class YFinanceProvider:
    provider_id = "yfinance"
    def supports(self, exchange, venue=None):
        return (
            (exchange in {Exchange.US, Exchange.HKEX, Exchange.LSE} and venue is None)
            or (exchange is Exchange.A_SHARE and venue in {Venue.SSE, Venue.SZSE})
        )
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

    def fetch_profile(self, request, symbol):
        try:
            yf = importlib.import_module("yfinance")
        except ImportError as exc:
            raise DependencyMissingError("Install the yfinance dependency") from exc
        try:
            info = getattr(yf.Ticker(symbol), "info", {}) or {}
            if not isinstance(info, dict):
                raise MalformedUpstreamError("Provider returned malformed company profile")
            name = info.get("longName") or info.get("shortName")
            if not name:
                raise NoDataError("No company profile was found for this ticker")
            market_cap = info.get("marketCap")
            if market_cap is not None:
                market_cap = float(market_cap)
                if not math.isfinite(market_cap):
                    market_cap = None
            currency = info.get("currency")
            company = {
                "name": str(name).strip(),
                "currency": currency,
                "country": info.get("country"),
                "sector": info.get("sectorDisp") or info.get("sector"),
                "industry": info.get("industryDisp") or info.get("industry"),
                "website": info.get("website"),
                "description": info.get("longBusinessSummary") or info.get("description"),
                "employees": _profile_int(info.get("fullTimeEmployees")),
            }
            return ProfileResult(company, market_cap, f"https://finance.yahoo.com/quote/{symbol}")
        except (NoDataError, DependencyMissingError, MalformedUpstreamError):
            raise
        except (TypeError, ValueError, AttributeError, KeyError) as exc:
            raise MalformedUpstreamError("Provider returned malformed company profile") from exc
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

    def fetch_profile(self, request, symbol):
        try:
            ak = importlib.import_module("akshare")
        except ImportError as exc:
            raise DependencyMissingError("Install the optional public-data-akshare dependency") from exc
        ticker = symbol.split(".", 1)[0]
        try:
            frame = ak.stock_individual_info_em(symbol=ticker)
            if frame is None or frame.empty or not {"item", "value"}.issubset(frame.columns):
                raise NoDataError("No company profile was found for this ticker")
            values = {str(row["item"]).strip(): row["value"] for _, row in frame.iterrows()}
            name = _first_text(values, ("股票简称", "公司名称", "名称", "name"))
            if not name:
                raise NoDataError("No company profile was found for this ticker")
            industry = _first_text(values, ("行业", "所属行业", "证监会行业", "申万行业"))
            company = {
                "name": name,
                "currency": "CNY",
                "country": "CN",
                "sector": industry,
                "industry": industry,
                "website": _first_text(values, ("网址", "公司网站", "官方网站")),
                "description": _first_text(values, ("公司简介", "主营业务", "经营范围", "公司业务")),
                "employees": _profile_int(_first_value(values, ("员工人数", "员工总数", "在职员工人数"))),
            }
            market_cap = _profile_float(_first_value(values, ("总市值", "总市值(元)")))
            return ProfileResult(company, market_cap, f"https://quote.eastmoney.com/{ticker}.html")
        except (NoDataError, DependencyMissingError, MalformedUpstreamError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError("A-share profile provider request failed", details={"retryable": True}) from exc

class FixtureProvider:
    provider_id = "fixture"
    def __init__(self, fixtures): self.fixtures = fixtures
    def supports(self, exchange, venue=None): return not (exchange is Exchange.A_SHARE and venue is Venue.BSE)
    def normalize_symbol(self, exchange, ticker, venue=None): return normalize_symbol(exchange, ticker, venue)
    def fetch(self, request):
        key = f"{request.exchange.value}:{request.venue.value if request.venue else ''}:{self.normalize_symbol(request.exchange, request.ticker, request.venue)}"
        if key not in self.fixtures: raise NoDataError("No fixture data for ticker")
        return self.fixtures[key]

    def fetch_profile(self, request, symbol):
        key = next((candidate for candidate in self.fixtures if candidate.endswith(f":{symbol}")), None)
        if key is None:
            raise NoDataError("No fixture data for ticker")
        result = self.fixtures[key]
        return ProfileResult(result.company, None, result.source_url)


def _first_value(values: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in values:
            return values[key]
    return None


def _first_text(values: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    value = _first_value(values, keys)
    text = str(value).strip() if value is not None else ""
    return text or None


def _profile_int(value: Any) -> int | None:
    try:
        return int(float(str(value).replace(",", "").strip())) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _profile_float(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").strip()) if value is not None and str(value).strip() else None
        return number if number is not None and math.isfinite(number) else None
    except (TypeError, ValueError):
        return None

def default_providers(live_enabled: bool = False):
    return [YFinanceProvider(), AkShareProvider()] if live_enabled else []


def select_provider(request, providers=None):
    for provider in providers or default_providers():
        if provider.supports(request.exchange, request.venue): return provider
    if request.exchange is Exchange.A_SHARE and request.venue is Venue.BSE: raise UnsupportedExchangeError("BSE capability is not approved")
    raise ProviderUnavailableError("Live public-data providers are disabled")
