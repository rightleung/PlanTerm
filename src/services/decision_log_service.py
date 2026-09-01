"""Session-scoped, immutable decision log service with no persistence."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from pydantic import ValidationError

from src.models.governance import DECISION_FIELDS, DecisionLogEntry


class DecisionLogValidationError(ValueError):
    """Structured fail-closed validation error for decision rows."""

    def __init__(self, error_type: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": self.message, "error_type": self.error_type, "details": self.details}


class DecisionLogService:
    """An in-memory log owned by one session; entries never cross instances."""

    def __init__(self, session_id: str | None = None, rows: list[DecisionLogEntry | dict] | None = None):
        self.session_id = session_id or uuid4().hex
        self._entries: list[DecisionLogEntry] = []
        for row in rows or []:
            self.append(row)

    def append(self, row: DecisionLogEntry | dict) -> dict:
        if isinstance(row, DecisionLogEntry):
            # Pydantic's frozen flag protects field reassignment, not nested
            # dictionaries/lists. Re-validate a defensive deep copy so the
            # caller cannot mutate an entry after it enters this session log.
            entry = DecisionLogEntry.model_validate(deepcopy(row.model_dump(mode="python")))
        elif isinstance(row, dict):
            unknown = sorted(set(row) - set(DECISION_FIELDS))
            missing = sorted(set(DECISION_FIELDS) - set(row))
            if unknown:
                raise DecisionLogValidationError("unexpected_input_key", "Decision row has unexpected fields", {"fields": unknown})
            if missing:
                raise DecisionLogValidationError("validation_error", "Decision row is incomplete", {"missing": missing})
            try:
                entry = DecisionLogEntry.model_validate(deepcopy(row))
            except ValidationError as exc:
                errors = [{"loc": list(item.get("loc", ())), "type": item.get("type", "validation_error"), "msg": item.get("msg", "Invalid value")} for item in exc.errors(include_url=False)]
                raise DecisionLogValidationError("validation_error", "Decision row failed validation", {"errors": errors}) from exc
        else:
            raise DecisionLogValidationError("invalid_input_row", "Decision row must be an object")
        if any(existing.decision_id == entry.decision_id for existing in self._entries):
            raise DecisionLogValidationError("duplicate_decision_id", "Decision rows are immutable and IDs cannot be reused", {"decision_id": entry.decision_id})
        self._entries.append(entry)
        return self._export_entry(entry)

    def rows(self) -> tuple[dict, ...]:
        return tuple(self._export_entry(entry) for entry in self._entries)

    def export(self) -> list[dict]:
        return list(self.rows())

    @property
    def entries(self) -> tuple[dict, ...]:
        return self.rows()

    record = append
    list_rows = rows

    @staticmethod
    def _export_entry(entry: DecisionLogEntry) -> dict:
        return deepcopy(entry.model_dump(mode="json"))


def seeded_decision_rows(case_id: str, as_of_date: str, decision_table: list[dict]) -> list[dict]:
    """Create deterministic evidence rows for the three displayed scenario conclusions."""
    rows = []
    for item in decision_table:
        variant = item["plan_variant"]
        rows.append({
            "decision_id": f"{case_id}-{variant}-scenario",
            "date": as_of_date,
            "context": f"FY2026 {variant} operating-plan conclusion",
            "options": ["base", "upside", "downside"],
            "decision": f"Use the {variant} plan variant for review",
            "rationale": "Scenario conclusion is calculated from the committed category and cash bridges.",
            "owner_role": "Group FP&A",
            "affected_contracts": ["decision_table", "cash_bridge", "reconciliation"],
            "evidence": [{
                "metric": "fy_revenue_delta",
                "value": item["fy_revenue_delta"],
                "formula": "selected FY2026 revenue - base FY2026 revenue",
                "source": "calculated category scenario rollup",
                "provenance": item["provenance"],
                "reconciliation_status": "reconciled",
            }, {
                "metric": "fy_operating_profit_delta",
                "value": item["fy_operating_profit_delta"],
                "formula": "selected FY2026 operating profit - base FY2026 operating profit",
                "source": "calculated category scenario rollup",
                "provenance": item["provenance"],
                "reconciliation_status": "reconciled",
            }],
            "supersedes": None,
            "status": "Approved" if variant == "base" else "Proposed",
        })
    return rows


DecisionLogRow = DecisionLogEntry
DecisionRow = DecisionLogEntry
DecisionLogEvent = DecisionLogEntry
