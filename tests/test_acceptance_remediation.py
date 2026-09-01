import csv
import io
import json
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from planterm import __version__
from src import __version__ as src_version
from src.api import app
from src.services.spreadsheet_neutralizer import neutralize_text, numeric_text, sanitize_csv_row


client = TestClient(app)


def test_spreadsheet_text_vectors_are_idempotent():
    vectors = {
        "=SUM(A1)": "'=SUM(A1)",
        "+1": "'+1",
        "-label": "'-label",
        "@cmd": "'@cmd",
        "plain label": "plain label",
    }
    for source, expected in vectors.items():
        assert neutralize_text(source) == expected
        assert neutralize_text(neutralize_text(source)) == expected
    assert numeric_text("-0.25", "volume_change_pct") == "-0.25"
    assert numeric_text(-0.25, "volume_change_pct") == "-0.25"


def test_csv_row_round_trip_keeps_typed_numeric_and_text_values():
    row = sanitize_csv_row({
        "case_id": "case-1",
        "plan_variant": "base",
        "period": "2026-07",
        "business_unit": "plain label",
        "category_id": "category-1",
        "volume_change_pct": "-0.25",
        "average_ticket_change_pct": "0.100000",
        "gross_margin_delta_pp": "0",
        "opex_ratio_delta_pp": "0.01",
    })
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row), lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    parsed = next(csv.DictReader(io.StringIO(output.getvalue())))
    assert parsed["business_unit"] == "plain label"
    assert float(parsed["volume_change_pct"]) == -0.25
    assert not parsed["volume_change_pct"].startswith("'")


def test_version_declarations_and_health_are_exactly_020():
    root = Path(__file__).parents[1]
    with (root / "pyproject.toml").open("rb") as handle:
        pyproject_version = tomllib.load(handle)["project"]["version"]
    config_text = (root / "src" / "config.py").read_text(encoding="utf-8")
    web_version = json.loads((root / "web" / "package.json").read_text(encoding="utf-8"))["version"]
    assert pyproject_version == __version__ == src_version == web_version == "0.2.0"
    assert 'version: str = "0.2.0"' in config_text
    assert client.get("/health").json()["version"] == "0.2.0"


def test_planning_template_numeric_columns_are_not_neutralized():
    response = client.get("/api/v1/cases/miniso-2026/planning-input-template")
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 252
    numeric_fields = ("volume_change_pct", "average_ticket_change_pct", "gross_margin_delta_pp", "opex_ratio_delta_pp")
    assert all(not row[field].startswith("'") for row in rows for field in numeric_fields)


@pytest.mark.parametrize("field,value", [
    ("validated", False),
    ("row_count", 251),
    ("planning_horizon", {"locked_through": "2026-01", "editable_from": "2026-02", "editable_to": "2026-06"}),
])
def test_preview_rejects_mutated_import_response_envelope(field, value):
    template = client.get("/api/v1/cases/miniso-2026/planning-input-template").content
    imported = client.post(
        "/api/v1/cases/miniso-2026/planning-inputs/import",
        content=template,
        headers={"Content-Type": "text/csv"},
    ).json()
    payload = {
        "selected_plan_variant": "base",
        "planning_input_source": "upload",
        "rows": imported["rows"],
        field: value,
    }
    response = client.post("/api/v1/cases/miniso-2026/dashboard/preview", json=payload)
    assert response.status_code == 422
    assert response.json()["error_type"] == "unexpected_input_key"
