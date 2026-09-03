"""Typed contracts for the stateless public financial-data preview."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Exchange(str, Enum):
    LSE = "LSE"
    A_SHARE = "A_SHARE"
    HKEX = "HKEX"
    US = "US"


class Venue(str, Enum):
    SSE = "SSE"
    SZSE = "SZSE"
    BSE = "BSE"


class PeriodSelection(str, Enum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    BOTH = "both"


PublicImportErrorCode = Literal[
    "invalid_exchange", "invalid_venue", "invalid_ticker", "ambiguous_ticker",
    "unsupported_exchange", "dependency_missing", "no_data", "malformed_upstream",
    "period_inconsistent", "currency_missing", "rate_limited", "provider_timeout",
    "provider_unavailable", "validation_error", "internal_server_error",
]


class PublicImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    exchange: Exchange
    ticker: str = Field(min_length=1, max_length=24)
    venue: Venue | None = None
    periods: PeriodSelection = PeriodSelection.BOTH
    include_profile: bool = False

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        if not value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError("Ticker is empty or contains control characters")
        if "://" in value or value.lower().startswith(("http:", "https:", "ftp:")):
            raise ValueError("Ticker must not be a URL")
        return value

    @model_validator(mode="after")
    def validate_venue(self) -> "PublicImportRequest":
        if self.exchange is Exchange.A_SHARE and self.venue is None:
            if self.ticker.strip().isdigit() and len(self.ticker.strip()) == 6:
                raise ValueError("A-share ticker requires an explicit venue")
            raise ValueError("A-share venue is required")
        if self.exchange is not Exchange.A_SHARE and self.venue is not None:
            raise ValueError("Venue is only valid for A_SHARE")
        return self


class StatementSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    url: str
    retrieved_at: datetime
    as_of: date | None = None
    filing_date: date | None = None
    normalization_version: str = "public-import-v1"


class NormalizedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_end: date
    period_type: Literal["annual", "quarterly"]
    fiscal_year: int
    fiscal_quarter: int | None = Field(default=None, ge=1, le=4)
    is_flow: bool
    currency: str = Field(min_length=3, max_length=3)
    unit: str
    unit_scale: Literal["native", "thousands", "millions"]
    values: dict[str, float | None]
    metric_semantics: dict[str, Literal["flow", "stock"]] = Field(default_factory=dict)
    source: StatementSource


class PublicImportMapping(BaseModel):
    dashboard_ready: bool = False
    reason: str


class PublicImportProvenance(BaseModel):
    provider: str
    source_urls: list[str]
    retrieved_at: datetime
    as_of: date | None = None
    normalization_version: str = "public-import-v1"


class PublicImportCompany(BaseModel):
    name: str | None = None
    currency: str | None = None
    country: str | None = None


class PublicImportRequestEcho(BaseModel):
    exchange: Exchange
    ticker: str
    venue: Venue | None = None
    normalized_symbol: str
    periods: PeriodSelection


class PublicImportPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str
    request: PublicImportRequestEcho
    company: PublicImportCompany
    statements: list[NormalizedStatement]
    mapping: PublicImportMapping
    disclosures: list[str]
    provenance: PublicImportProvenance


class PublicImportErrorDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    exchange: Exchange | None = None
    venue: Venue | None = None
    normalized_symbol: str | None = None
    provider: str | None = None
    retryable: bool | None = None


class PublicImportError(BaseModel):
    error: str
    error_type: PublicImportErrorCode
    details: dict[str, Any] | None = None
