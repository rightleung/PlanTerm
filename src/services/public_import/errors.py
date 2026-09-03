"""Redaction-safe public-import service errors."""

from __future__ import annotations

from typing import Any

from src.models.public_import import PublicImportErrorCode


class PublicImportException(Exception):
    def __init__(
        self,
        error_type: PublicImportErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details or {}


class InvalidExchangeError(PublicImportException):
    def __init__(self, message="Invalid exchange", details=None):
        super().__init__("invalid_exchange", message, details)


class InvalidVenueError(PublicImportException):
    def __init__(self, message="Invalid venue", details=None):
        super().__init__("invalid_venue", message, details)


class InvalidTickerError(PublicImportException):
    def __init__(self, message="Invalid ticker", details=None):
        super().__init__("invalid_ticker", message, details)


class AmbiguousTickerError(PublicImportException):
    def __init__(self, message="Ticker is ambiguous", details=None):
        super().__init__("ambiguous_ticker", message, details)


class UnsupportedExchangeError(PublicImportException):
    def __init__(self, message="Exchange or venue is unsupported", details=None):
        super().__init__("unsupported_exchange", message, details)


class DependencyMissingError(PublicImportException):
    def __init__(self, message="Optional provider dependency is unavailable", details=None):
        super().__init__("dependency_missing", message, details)


class NoDataError(PublicImportException):
    def __init__(self, message="No public data found", details=None):
        super().__init__("no_data", message, details)


class MalformedUpstreamError(PublicImportException):
    def __init__(self, message="Provider returned malformed data", details=None):
        super().__init__("malformed_upstream", message, details)


class PeriodInconsistentError(PublicImportException):
    def __init__(self, message="Provider periods are inconsistent", details=None):
        super().__init__("period_inconsistent", message, details)


class CurrencyMissingError(PublicImportException):
    def __init__(self, message="Provider currency is missing or ambiguous", details=None):
        super().__init__("currency_missing", message, details)


class RateLimitedError(PublicImportException):
    def __init__(self, message="Provider rate limit reached", details=None):
        super().__init__("rate_limited", message, details)


class ProviderTimeoutError(PublicImportException):
    def __init__(self, message="Provider request timed out", details=None):
        super().__init__("provider_timeout", message, details)


class ProviderUnavailableError(PublicImportException):
    def __init__(self, message="Provider is unavailable", details=None):
        super().__init__("provider_unavailable", message, details)
