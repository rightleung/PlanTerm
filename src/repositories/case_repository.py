"""File-backed repository for the committed deterministic case."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from src.config import ROOT_DIR
from src.models.planning import PlanningRecord


@dataclass(frozen=True)
class CaseData:
    case_id: str
    metadata: dict
    assumptions: dict
    records: tuple[PlanningRecord, ...]


class CaseNotFoundError(LookupError):
    pass


class CaseRepository:
    def __init__(self, case_dir: str | Path | None = None):
        self.case_dir = Path(case_dir or ROOT_DIR / "data" / "cases")

    def list_cases(self) -> list[dict]:
        cases = []
        for metadata_path in sorted(self.case_dir.glob("*/metadata.json")):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            cases.append({
                "case_id": metadata["case_id"],
                "name": metadata["name"],
                "planning_year": metadata["planning_year"],
                "as_of_date": metadata["as_of_date"],
                "currency": metadata["currency"],
            })
        return cases

    def get_case(self, case_id: str) -> CaseData:
        case_path = self.case_dir / case_id
        if not case_path.is_dir():
            raise CaseNotFoundError(case_id)
        metadata = json.loads((case_path / "metadata.json").read_text(encoding="utf-8"))
        assumptions = json.loads((case_path / "assumptions.json").read_text(encoding="utf-8"))
        records: list[PlanningRecord] = []
        with (case_path / "planning_records.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                records.append(PlanningRecord(
                    period=row["period"],
                    scenario=row["scenario"],
                    brand=row["brand"],
                    market=row["market"],
                    business_unit=row["business_unit"],
                    metric=row["metric"],
                    value=None if row["value"] in {"", "null", "None"} else float(row["value"]),
                    unit=row["unit"],
                    provenance=row["provenance"],
                ))
        return CaseData(metadata["case_id"], metadata, assumptions, tuple(records))
