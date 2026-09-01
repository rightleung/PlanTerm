"""Strict, JSON-safe governance contracts for operating-plan decisions."""

from __future__ import annotations

from datetime import date
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DECISION_FIELDS = (
    "decision_id",
    "date",
    "context",
    "options",
    "decision",
    "rationale",
    "owner_role",
    "affected_contracts",
    "evidence",
    "supersedes",
    "status",
)


def _json_safe(value: Any, path: str = "evidence") -> Any:
    """Validate and return a JSON-safe value without coercing hidden data."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain finite numbers")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{path} keys must be strings")
        return {key: _json_safe(item, f"{path}.{key}") for key, item in value.items()}
    raise ValueError(f"{path} must contain JSON-safe values")


class DecisionLogEntry(BaseModel):
    """Immutable event row. The field set is intentionally closed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1)
    date: str
    context: str = Field(min_length=1)
    options: tuple[str, ...] = Field(min_length=1)
    decision: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    affected_contracts: tuple[str, ...] = Field(min_length=1)
    evidence: Any
    supersedes: str | None = None
    status: str = Field(min_length=1)

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("date must be an ISO-8601 date") from exc
        return value

    @field_validator("options", "affected_contracts", mode="before")
    @classmethod
    def valid_string_list(cls, value: Any) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("must be a non-empty list of strings")
        return tuple(value)

    @field_validator("evidence", mode="before")
    @classmethod
    def valid_evidence(cls, value: Any) -> Any:
        return _json_safe(value)

    @model_validator(mode="after")
    def complete_row(self) -> "DecisionLogEntry":
        if self.supersedes == self.decision_id:
            raise ValueError("supersedes cannot reference the same decision")
        return self


class AssumptionRegistry(BaseModel):
    """Build and provenance metadata for deterministic planning assumptions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    assumption_version: str = Field(min_length=1)
    git_sha: str = Field(min_length=1)
    provenance_labels: dict[str, str]
    as_of_date: str
    currency: str = "RMB"
    unit: str = "RMB millions"
