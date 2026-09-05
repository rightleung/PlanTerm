from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from src.models.public_import import Exchange, NormalizedStatement, PeriodSelection, PublicImportRequest, StatementSource, Venue
from .errors import AmbiguousTickerError, CurrencyMissingError, InvalidTickerError, PeriodInconsistentError, MalformedUpstreamError

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,24}$")

COMMON_METRIC_SEMANTICS = {
    "revenue": "flow",
    "gross_profit": "flow",
    "operating_profit": "flow",
    "operating_expense": "flow",
    "cost_of_sales": "flow",
    "cash": "stock",
    "total_assets": "stock",
    "total_liabilities": "stock",
    "operating_cf": "flow",
}

_METRIC_ALIASES = {
    "revenue": "revenue", "total_revenue": "revenue",
    "gross_profit": "gross_profit",
    "operating_income": "operating_profit", "operating_profit": "operating_profit",
    "operating_expense": "operating_expense", "operating_expenses": "operating_expense",
    "cost_of_revenue": "cost_of_sales", "cost_of_sales": "cost_of_sales", "cost_of_goods_sold": "cost_of_sales",
    "cash": "cash", "cash_and_cash_equivalents": "cash", "cash_cash_equivalents_and_short_term_investments": "cash",
    "total_assets": "total_assets",
    "total_liab": "total_liabilities", "total_liabilities": "total_liabilities", "total_liabilities_net_minority_interest": "total_liabilities",
    "operating_cash_flow": "operating_cf", "cash_from_operating_activities": "operating_cf", "operating_cf": "operating_cf",
}


def canonical_metric(value: Any) -> str | None:
    token = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return _METRIC_ALIASES.get(token)


def normalize_symbol(exchange: Exchange, ticker: str, venue: Venue | None = None) -> str:
    if not isinstance(ticker, str):
        raise InvalidTickerError()
    t = ticker.strip().upper()
    if (
        not _TICKER_RE.fullmatch(t)
        or any(ord(c) < 32 or ord(c) == 127 for c in t)
        or "://" in t
        or t.startswith(("HTTP:", "HTTPS:", "FTP:"))
    ):
        raise InvalidTickerError()
    if exchange is Exchange.US:
        if t.endswith((".US", ".NYSE", ".NASDAQ")):
            raise InvalidTickerError("US ticker contains an unapproved suffix")
        return t.replace(".", "-")
    if exchange is Exchange.HKEX:
        if t.endswith(".HK"):
            t = t[:-3]
        if not t.isdigit() or not 1 <= len(t) <= 5:
            raise InvalidTickerError("HKEX ticker must contain 1-5 digits")
        return f"{int(t):04d}.HK"
    if exchange is Exchange.LSE:
        if "." in t and not t.endswith(".L"):
            raise InvalidTickerError("LSE ticker contains an unapproved suffix")
        base = t[:-2] if t.endswith(".L") else t
        if not re.fullmatch(r"[A-Z0-9-]{1,12}", base):
            raise InvalidTickerError("LSE ticker must be an approved symbol")
        return f"{base}.L"
    if exchange is Exchange.A_SHARE:
        if venue is None:
            raise AmbiguousTickerError("A-share ticker requires SSE, SZSE or BSE venue")
        suffixes = {Venue.SSE: (".SS", ".SH"), Venue.SZSE: (".SZ",), Venue.BSE: (".BSE",)}
        for suffix in suffixes[venue]:
            if t.endswith(suffix):
                t = t[:-len(suffix)]
                break
        if not t.isdigit() or len(t) != 6:
            raise InvalidTickerError("A-share ticker must be six digits")
        if venue is Venue.SSE:
            return f"{t}.SS"
        if venue is Venue.SZSE:
            return f"{t}.SZ"
        return f"{t}.BSE"
    raise InvalidTickerError()


_DEFAULT_CURRENCIES = {
    Exchange.US: "USD",
    Exchange.HKEX: "HKD",
    Exchange.LSE: "GBP",
    Exchange.A_SHARE: "CNY",
}


def _currency(value: Any, fallback: str | None = None) -> str:
    currency = str(value or fallback or "").upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise CurrencyMissingError()
    return currency


def _source_datetime(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        value = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise ValueError("retrieved_at")


def _date(value: Any, field: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(field)


def _source_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("source_url")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("source_url")
    return value


def _unit_scale(value: Any, unit: Any) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        unit_text = str(unit or "").strip().lower()
        if re.search(r"\b(millions?|mm|mn)\b", unit_text):
            candidate = "millions"
        elif re.search(r"\b(thousands?|k)\b", unit_text):
            candidate = "thousands"
        else:
            candidate = "native"
    aliases = {"native": "native", "raw": "native", "thousand": "thousands", "thousands": "thousands", "k": "thousands", "million": "millions", "millions": "millions", "m": "millions"}
    if candidate not in aliases:
        raise ValueError("unit_scale")
    return aliases[candidate]


def normalize_statements(raw: list[dict[str, Any]], request: PublicImportRequest, provider_id: str, source_url: str, company_currency: str | None = None) -> list[NormalizedStatement]:
    if not isinstance(raw, list) or not raw:
        raise MalformedUpstreamError("Provider returned no statement rows")
    try:
        source_url = _source_url(source_url)
    except Exception as exc:
        raise MalformedUpstreamError("Provider returned an unapproved source URL") from exc
    result: list[NormalizedStatement] = []
    seen: dict[tuple[date, str], NormalizedStatement] = {}
    for row in raw:
        try:
            if not isinstance(row, dict):
                raise ValueError("row")
            period_end = _date(row.get("period_end"), "period_end")
            if period_end is None:
                raise ValueError("period_end")
            period_type = str(row["period_type"]).lower()
            if period_type not in {"annual", "quarterly"}:
                raise PeriodInconsistentError()
            if request.periods is PeriodSelection.ANNUAL and period_type != "annual": continue
            if request.periods is PeriodSelection.QUARTERLY and period_type != "quarterly": continue
            key = (period_end, period_type)
            values = row.get("values")
            if not isinstance(values, dict) or not values:
                raise ValueError("values")
            clean_values: dict[str, float | None] = {}
            for raw_metric, raw_value in values.items():
                metric = canonical_metric(raw_metric)
                if metric is None:
                    raise ValueError("unknown metric")
                number = None if raw_value is None else float(raw_value)
                if metric in clean_values and clean_values[metric] != number:
                    raise ValueError("conflicting metric aliases")
                clean_values[metric] = number
            if any(v is not None and not math.isfinite(v) for v in clean_values.values()):
                raise ValueError("nonfinite")
            metric_semantics = {metric: COMMON_METRIC_SEMANTICS[metric] for metric in clean_values}
            explicit_semantics = row.get("metric_semantics")
            if explicit_semantics is not None:
                if not isinstance(explicit_semantics, dict):
                    raise ValueError("metric_semantics")
                for raw_metric, semantic in explicit_semantics.items():
                    metric = canonical_metric(raw_metric)
                    if metric not in metric_semantics or semantic != metric_semantics[metric]:
                        raise ValueError("metric_semantics")
            currency = _currency(row.get("currency"), company_currency or _DEFAULT_CURRENCIES[request.exchange])
            unit = str(row.get("unit") or "").strip()
            unit_scale = _unit_scale(row.get("unit_scale"), unit)
            if not unit:
                unit = f"{currency} {unit_scale}"
            retrieved = _source_datetime(row.get("retrieved_at"))
            raw_fiscal_year = row.get("fiscal_year")
            fiscal_year = period_end.year if raw_fiscal_year is None else int(raw_fiscal_year)
            # Annual rows conventionally identify the fiscal year by their
            # ending year. Quarterly rows may legitimately end in the prior
            # calendar year for a non-calendar fiscal year (for example Q3
            # ending in December for a March year-end).
            if period_type == "annual" and fiscal_year != period_end.year:
                raise PeriodInconsistentError("Provider returned a fiscal year that does not match period_end")
            statement = NormalizedStatement(
                period_end=period_end,
                period_type=period_type,
                fiscal_year=fiscal_year,
                fiscal_quarter=None if period_type == "annual" else row.get("fiscal_quarter"),
                # Keep the legacy row-level flag for compatibility, while the
                # per-metric map is authoritative for mixed flow/stock rows.
                is_flow=all(semantic == "flow" for semantic in metric_semantics.values()),
                currency=currency,
                unit=unit,
                unit_scale=unit_scale,
                values=clean_values,
                metric_semantics=metric_semantics,
                source=StatementSource(
                    provider=provider_id,
                    url=source_url,
                    retrieved_at=retrieved,
                    as_of=_date(row.get("as_of"), "as_of"),
                    filing_date=_date(row.get("filing_date"), "filing_date"),
                ),
            )
            previous = seen.get(key)
            if previous is not None:
                comparable = (previous.fiscal_year, previous.fiscal_quarter, previous.is_flow, previous.currency, previous.unit, previous.unit_scale, previous.values, previous.metric_semantics)
                current = (statement.fiscal_year, statement.fiscal_quarter, statement.is_flow, statement.currency, statement.unit, statement.unit_scale, statement.values, statement.metric_semantics)
                if comparable != current:
                    raise PeriodInconsistentError("Provider returned conflicting rows for one period")
                continue
            seen[key] = statement
            result.append(statement)
        except (CurrencyMissingError, PeriodInconsistentError):
            raise
        except Exception as exc: raise MalformedUpstreamError("Provider returned malformed statement data") from exc
    if not result:
        return []
    currencies = {statement.currency for statement in result}
    if len(currencies) != 1:
        raise CurrencyMissingError("Provider returned inconsistent statement currencies")
    return sorted(result, key=lambda s: (s.period_end, s.period_type), reverse=True)
