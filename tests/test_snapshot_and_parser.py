import json

import pytest

from scripts.refresh_public_actuals import SnapshotParseError, parse_public_html


def test_public_snapshot_has_required_schema_and_provenance():
    snapshot = json.loads(open("data/source/miniso_public_actuals.json", encoding="utf-8").read())
    assert snapshot["company"] == "MINISO Group Holding Limited"
    assert snapshot["tickers"] == {"NYSE": "MNSO", "HKEX": "9896"}
    assert set(snapshot["periods"]) == {"FY2025", "2025 H1", "2026 Q1", "2026 Q2", "2026 H1"}
    for period in snapshot["periods"].values():
        assert period["source_url"].startswith("https://")
        assert period["source_date"]
        assert period["period_end"]
        assert period["provenance"] == "public_reported"
        assert {"Revenue", "Cost of Sales", "Gross Profit", "Operating Profit", "Adjusted EBITDA", "Operating Cash Flow", "CAPEX", "FCF"} <= set(period["metrics"])


def test_refresh_parser_reads_minimal_html_fixture():
    fixture = """
    <html><body><table id='selected-financial-information'>
      <tr><th>Revenue</th><td>11,498.9</td></tr>
      <tr><th>Gross profit</th><td>5,093.7</td></tr>
      <tr><th>Operating profit</th><td>1,639.9</td></tr>
      <tr><th>Adjusted EBITDA</th><td>2,255.5</td></tr>
      <tr><th>Net cash from operating activities</th><td>1,475.4</td></tr>
      <tr><th>CAPEX</th><td>724.6</td></tr>
      <tr><th>Free cash flow</th><td>750.8</td></tr>
    </table></body></html>
    """
    parsed = parse_public_html(fixture, "https://example.com/source", "2026-08-28")
    assert parsed["metrics"]["Revenue"] == 11498.9
    assert parsed["metrics"]["FCF"] == 750.8


def test_refresh_parser_reads_cash_metrics_from_published_prose():
    fixture = """
    <html><body><table id='selected-financial-information'>
      <tr><th>Revenue</th><td>11,498.9</td></tr>
      <tr><th>Gross profit</th><td>5,093.7</td></tr>
      <tr><th>Operating profit</th><td>1,639.9</td></tr>
      <tr><th>Adjusted EBITDA</th><td>2,255.5</td></tr>
    </table>
    <p>Net cash from operating activities was RMB1,475.4 million for 26H1.</p>
    <p>Capital expenditure was RMB724.6 million and free cash flow was RMB750.8 million.</p>
    </body></html>
    """
    parsed = parse_public_html(fixture, "https://example.com/source", "2026-08-28")
    assert parsed["metrics"]["Operating Cash Flow"] == 1475.4
    assert parsed["metrics"]["CAPEX"] == 724.6
    assert parsed["metrics"]["FCF"] == 750.8


@pytest.mark.parametrize("html", ["<html></html>", "<table><tr><td>Revenue</td><td>1</td></tr></table>"])
def test_refresh_parser_fails_loudly_when_structure_or_fields_change(html):
    with pytest.raises(SnapshotParseError):
        parse_public_html(html, "https://example.com/source", "2026-08-28")
