from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_openapi_freezes_the_v1_endpoint_surface():
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert {
        "/api/v1/cases/{case_id}/dashboard",
        "/api/v1/cases/{case_id}/planning-input-template",
        "/api/v1/cases/{case_id}/planning-inputs/import",
        "/api/v1/cases/{case_id}/dashboard/preview",
        "/api/v1/cases/{case_id}/operating-plan",
        "/api/v1/cases/{case_id}/operating-plan/preview",
        "/api/v1/cases/{case_id}/forecast-accuracy",
        "/api/v1/public-import/preview",
    } <= set(paths)
    assert "get" in paths["/api/v1/cases/{case_id}/operating-plan"]
    assert "post" in paths["/api/v1/cases/{case_id}/operating-plan/preview"]
    assert "post" in paths["/api/v1/public-import/preview"]


def test_public_import_contract_is_additive_and_stateless():
    types = (ROOT / "web/src/types/planning.ts").read_text(encoding="utf-8")
    api_client = (ROOT / "web/src/api/client.ts").read_text(encoding="utf-8")
    service = (ROOT / "src/services/public_import/service.py").read_text(encoding="utf-8")
    assert "PublicImportPreview" in types
    assert "previewPublicImport" in api_client
    assert "dashboard_ready=False" in service
    assert "no FX conversion" in service
    assert "miniso-2026" not in service


def test_additive_release_identifier_preserves_legacy_version_contract():
    health = client.get("/health").json()
    assert health["version"] == "0.2.0"
    assert health["release_id"] == "1.1.0-rc.1"


def test_typescript_freezes_additive_governance_fields():
    types = (ROOT / "web/src/types/planning.ts").read_text(encoding="utf-8")
    for field in ("decision_log", "assumption_registry", "assumption_version", "git_sha", "GovernanceEvidence"):
        assert field in types
    for field in ("decision_id", "date", "context", "options", "decision", "rationale", "owner_role", "affected_contracts", "evidence", "supersedes", "status"):
        assert field in types


def test_governance_provenance_marks_derived_margin_as_calculated():
    panel = (ROOT / "web/src/features/governance/ProvenancePanel.tsx").read_text(encoding="utf-8")
    assert "const derived = kpi.metric === 'operating_margin' || kpi.variance_amount !== null" in panel
    assert "provenance: derived ? 'calculated'" in panel
    assert "PUBLIC_ANCHOR_METRICS" in panel


def test_profit_bridge_is_exposed_across_api_types_ui_and_workbook():
    models = (ROOT / "src/models/planning.py").read_text(encoding="utf-8")
    types = (ROOT / "web/src/types/planning.ts").read_text(encoding="utf-8")
    app = (ROOT / "web/src/App.tsx").read_text(encoding="utf-8")
    export = (ROOT / "web/src/export/managementPack.ts").read_text(encoding="utf-8")
    assert "class ProfitBridge" in models
    assert "profit_bridge: ProfitBridge" in models
    assert "export interface ProfitBridge" in types
    assert "<ProfitBridge bridge={dashboard.profit_bridge}" in app
    assert "Operating Profit bridge" in export
    assert "PVM profit effect + GM effect + Opex effect" in export


def test_management_pack_preserves_existing_seven_sheets_and_embeds_workforce_in_operating_decision():
    export = (ROOT / "web/src/export/managementPack.ts").read_text(encoding="utf-8")
    assert "workbook.addWorksheet('Assumptions & Sources')" in export
    assert "workbook.addWorksheet('Workforce Capacity')" not in export
    assert "function addWorkforceSection" in export
    assert "addWorkforceSection(operating, workforce)" in export


def test_frontend_lint_ignores_generated_browser_artifacts():
    config = (ROOT / "web/eslint.config.js").read_text(encoding="utf-8")
    assert "test-results" in config
    assert "playwright-report" in config
