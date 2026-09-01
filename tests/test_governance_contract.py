import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.models.governance import DecisionLogEntry
from src.repositories.case_repository import CaseRepository
from src.services.assumption_registry import build_assumption_registry
from src.services.decision_log_service import DecisionLogService, DecisionLogValidationError


client = TestClient(app)


def _row(decision_id="d-1"):
    return {
        "decision_id": decision_id,
        "date": "2026-06-30",
        "context": "FY2026 planning",
        "options": ["base", "upside"],
        "decision": "Use base",
        "rationale": "Reconciled committed scenario",
        "owner_role": "Group FP&A",
        "affected_contracts": ["decision_table"],
        "evidence": [{"metric": "revenue", "formula": "selected - base", "source": "calculated", "provenance": "calculated", "reconciliation_status": "reconciled"}],
        "supersedes": None,
        "status": "approved",
    }


def test_decision_log_is_immutable_and_session_scoped():
    first = DecisionLogService(session_id="one")
    exported = first.append(_row())
    exported["evidence"][0]["metric"] = "tampered"
    assert first.rows()[0]["evidence"][0]["metric"] == "revenue"
    entry = DecisionLogEntry.model_validate(_row("model-entry"))
    first.append(entry)
    entry.evidence[0]["metric"] = "tampered again"
    assert first.rows()[1]["evidence"][0]["metric"] == "revenue"
    assert DecisionLogService(session_id="two").rows() == ()
    with pytest.raises(DecisionLogValidationError) as duplicate:
        first.append(_row())
    assert duplicate.value.error_type == "duplicate_decision_id"


def test_decision_log_rejects_malformed_unknown_and_derived_fields():
    missing = _row()
    del missing["rationale"]
    with pytest.raises(DecisionLogValidationError) as error:
        DecisionLogService().append(missing)
    assert error.value.error_type == "validation_error"
    with pytest.raises(DecisionLogValidationError) as error:
        DecisionLogService().append({**_row(), "created_at": "now"})
    assert error.value.error_type == "unexpected_input_key"
    with pytest.raises(DecisionLogValidationError) as error:
        DecisionLogService().append({**_row(), "evidence": {"bad": {1, 2}}})
    assert error.value.error_type == "validation_error"


def test_assumption_registry_is_deterministic_and_safe():
    case = CaseRepository().get_case("miniso-2026")
    first = build_assumption_registry(case)
    second = build_assumption_registry(case)
    assert first == second
    assert first["assumption_version"]
    assert first["git_sha"]
    assert first["provenance_labels"]
    assert first["as_of_date"] == "2026-06-30"


def test_operating_plan_governance_is_additive_and_evidenced():
    response = client.get("/api/v1/cases/miniso-2026/operating-plan")
    assert response.status_code == 200
    payload = response.json()
    assert payload["assumption_registry"]["unit"] == "RMB millions"
    assert len(payload["decision_log"]) == 3
    assert {row["decision_id"] for row in payload["decision_log"]} == {
        "miniso-2026-base-scenario", "miniso-2026-upside-scenario", "miniso-2026-downside-scenario"
    }
    for row in payload["decision_table"]:
        assert row["evidence"][0]["metric"]
        assert row["evidence"][0]["formula"]
        assert row["evidence"][0]["source"]
        assert row["evidence"][0]["reconciliation_status"] == "reconciled"
