"""File-backed repository for the committed deterministic case."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.config import ROOT_DIR
from src.models.planning import PlanningRecord
from src.services.case_builder import validate_case_records
from src.services.committed_json import load_committed_json


@dataclass(frozen=True)
class CaseData:
    case_id: str
    metadata: dict
    assumptions: dict
    records: tuple[PlanningRecord, ...]
    taxonomy: dict | None = None
    category_seed: tuple[dict, ...] = ()
    working_capital_seed: tuple[dict, ...] = ()
    cash_assumptions: dict = field(default_factory=dict)
    forecast_snapshots: tuple[dict, ...] = ()


class CaseNotFoundError(LookupError):
    pass


def _validate_category_taxonomy(taxonomy: dict) -> None:
    """Reject taxonomy metadata that cannot meet the committed provenance contract."""
    categories = taxonomy.get("categories")
    registry = taxonomy.get("official_label_registry")
    if not isinstance(categories, list) or len(categories) != 14:
        raise ValueError("Committed category taxonomy must contain 14 planning leaves")
    leaf_keys = {(item.get("business_unit"), item.get("category_id")) for item in categories}
    if len(leaf_keys) != 14 or any(item.get("provenance") != "synthetic_allocation" for item in categories):
        raise ValueError("Committed category planning leaves are invalid")
    if not isinstance(registry, list) or len(registry) != 19:
        raise ValueError("Committed taxonomy must contain the 19 official source labels")
    expected_labels = {
        "MINISO": {"home decor", "small electronics", "textiles", "accessories", "beauty tools", "toys", "cosmetics", "personal care", "snacks", "fragrances and perfumes", "stationery and gifts"},
        "TOP_TOY": {"blind boxes", "toy bricks", "model figures", "model kits", "collectible dolls", "Ichiban Kuji", "sculptures", "other popular toys"},
    }
    actual_labels = {
        brand: {item.get("source_label") for item in registry if item.get("brand") == brand}
        for brand in expected_labels
    }
    if actual_labels != expected_labels:
        raise ValueError("Committed taxonomy official-label registry does not match the source")
    if len({item.get("source_label") for item in registry}) != 19:
        raise ValueError("Committed taxonomy contains duplicate official source labels")
    planning_ids = {item.get("category_id") for item in categories}
    for item in registry:
        if item.get("planning_category_id") not in planning_ids:
            raise ValueError("Committed taxonomy maps an official label to an unknown planning category")
        if item.get("source_url") != "https://ir.miniso.com/image/2023_ESG_Report.pdf" or item.get("source_period") != "Fiscal year ended June 30, 2023":
            raise ValueError("Committed taxonomy official-label provenance is incomplete")


class CaseRepository:
    def __init__(self, case_dir: str | Path | None = None):
        self.case_dir = Path(case_dir or ROOT_DIR / "data" / "cases")

    def list_cases(self) -> list[dict]:
        cases = []
        for metadata_path in sorted(self.case_dir.glob("*/metadata.json")):
            metadata = load_committed_json(metadata_path)
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
        metadata = load_committed_json(case_path / "metadata.json")
        assumptions = load_committed_json(case_path / "assumptions.json")
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
        validate_case_records(records)
        taxonomy_path = case_path / "category_taxonomy.json"
        seed_path = case_path / "category_scenario_seed.csv"
        taxonomy = load_committed_json(taxonomy_path) if taxonomy_path.exists() else None
        if taxonomy is not None:
            _validate_category_taxonomy(taxonomy)
        category_seed = []
        if seed_path.exists():
            with seed_path.open(newline="", encoding="utf-8") as handle:
                category_seed = list(csv.DictReader(handle))
        wc_path = case_path / "working_capital_seed.csv"
        working_capital_seed = tuple(csv.DictReader(wc_path.open(newline="", encoding="utf-8"))) if wc_path.exists() else ()
        cash_path = case_path / "cash_assumptions.json"
        cash_assumptions = load_committed_json(cash_path) if cash_path.exists() else {}
        snapshot_path = case_path / "forecast_snapshots.csv"
        forecast_snapshots = tuple(csv.DictReader(snapshot_path.open(newline="", encoding="utf-8"))) if snapshot_path.exists() else ()
        return CaseData(metadata["case_id"], metadata, assumptions, tuple(records), taxonomy, tuple(category_seed), working_capital_seed, cash_assumptions, forecast_snapshots)
