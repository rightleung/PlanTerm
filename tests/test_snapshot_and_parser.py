import json

import pytest

from scripts.refresh_public_actuals import SnapshotParseError, parse_public_html, validate_refresh_payload


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
      <tr><th>Cost of sales</th><td>6,405.2</td></tr>
      <tr><th>Gross profit</th><td>5,093.7</td></tr>
      <tr><th>Operating profit</th><td>1,639.9</td></tr>
      <tr><th>Adjusted EBITDA</th><td>2,255.5</td></tr>
      <tr><th>Net cash from operating activities</th><td>1,475.4</td></tr>
      <tr><th>CAPEX</th><td>724.6</td></tr>
      <tr><th>Free cash flow</th><td>750.8</td></tr>
      <tr><th>-Chinese mainland</th><td>6,453.955</td></tr>
      <tr><th>-Overseas markets</th><td>4,059.270</td></tr>
      <tr><th>TOP TOY Brand</th><td>984.618</td></tr>
      <tr><th>Others</th><td>1.058</td></tr>
    </table></body></html>
    """
    parsed = parse_public_html(fixture, "https://example.com/source", "2026-08-28")
    assert parsed["metrics"]["Revenue"] == 11498.9
    assert parsed["metrics"]["Cost of Sales"] == 6405.2
    assert parsed["metrics"]["FCF"] == 750.8
    assert parsed["revenue_split"] == {"MINISO Mainland": 6453.955, "MINISO Overseas": 4059.27, "TOP TOY": 984.618, "Others": 1.058}


def test_refresh_parser_reads_cash_metrics_from_published_prose():
    fixture = """
    <html><body><table id='selected-financial-information'>
      <tr><th>Revenue</th><td>11,498.9</td></tr>
      <tr><th>Cost of sales</th><td>6,405.2</td></tr>
      <tr><th>Gross profit</th><td>5,093.7</td></tr>
      <tr><th>Operating profit</th><td>1,639.9</td></tr>
      <tr><th>Adjusted EBITDA</th><td>2,255.5</td></tr>
      <tr><th>-Chinese mainland</th><td>6,453.955</td></tr>
      <tr><th>-Overseas markets</th><td>4,059.270</td></tr>
      <tr><th>TOP TOY Brand</th><td>984.618</td></tr>
      <tr><th>Others</th><td>1.058</td></tr>
    </table>
    <p>Net cash from operating activities was RMB1,475.4 million for 26H1.</p>
    <p>Capital expenditure was RMB724.6 million and free cash flow was RMB750.8 million.</p>
    </body></html>
    """
    parsed = parse_public_html(fixture, "https://example.com/source", "2026-08-28")
    assert parsed["metrics"]["Operating Cash Flow"] == 1475.4
    assert parsed["metrics"]["CAPEX"] == 724.6
    assert parsed["metrics"]["FCF"] == 750.8


def test_refresh_parser_scales_detailed_thousand_unit_values():
    fixture = """
    <html><body><table>
      <tr><th>Revenue</th><td>4,966,068</td><td>5,810,513</td><td>856,364</td><td>9,393,112</td><td>11,498,901</td><td>1,694,728</td></tr>
      <tr><th>Cost of sales</th><td>(2,767,187)</td><td>(3,180,868)</td><td>(468,802)</td><td>(5,236,194)</td><td>(6,405,225)</td><td>(944,013)</td></tr>
      <tr><th>Gross profit</th><td>2,198,881</td><td>2,629,645</td><td>387,562</td><td>4,156,918</td><td>5,093,676</td><td>750,715</td></tr>
      <tr><th>Operating profit</th><td>836,162</td><td>118,501</td><td>17,464</td><td>1,545,949</td><td>1,639,910</td><td>241,693</td></tr>
      <tr><th>Adjusted EBITDA</th><td>1,150,306</td><td>1,149,800</td><td>169,458</td><td>2,187,605</td><td>2,255,529</td><td>332,425</td></tr>
      <tr><th>-Chinese mainland</th><td>2,621,212</td><td>3,221,701</td><td>474,820</td><td>5,114,987</td><td>6,453,955</td><td>951,195</td></tr>
      <tr><th>-Overseas markets</th><td>1,942,014</td><td>2,118,122</td><td>312,173</td><td>3,534,017</td><td>4,059,270</td><td>598,262</td></tr>
      <tr><th>TOP TOY Brand</th><td>402,208</td><td>470,133</td><td>69,289</td><td>742,058</td><td>984,618</td><td>145,115</td></tr>
      <tr><th>Others</th><td>634</td><td>557</td><td>82</td><td>2,050</td><td>1,058</td><td>156</td></tr>
    </table>
    <p>Net cash from operating activities was RMB1,475.4 million.</p>
    <p>Capital expenditure was RMB724.6 million and free cash flow was RMB750.8 million.</p>
    </body></html>
    """
    parsed = parse_public_html(fixture, "https://example.com/source", "2026-08-28")
    assert parsed["metrics"]["Revenue"] == 11498.901
    assert parsed["metrics"]["Cost of Sales"] == 6405.225
    assert parsed["metrics"]["Adjusted EBITDA"] == 2255.529
    assert parsed["revenue_split"]["MINISO Mainland"] == 6453.955


def test_refresh_payload_validates_source_units_and_rollups():
    html = "<html><body>RMB million</body></html>"
    parsed = {
        "period_end": "2026-06-30",
        "source_url": "https://ir.miniso.com/2026-08-28-MINISO-Group-Announces-2026-June-Quarter-and-Interim-Unaudited-Financial-Results",
        "metrics": {"Revenue": 100.0, "Cost of Sales": 60.0, "Gross Profit": 40.0, "Operating Profit": 10.0, "Adjusted EBITDA": 15.0, "Operating Cash Flow": 12.0, "CAPEX": 5.0, "FCF": 7.0},
        "revenue_split": {"MINISO Mainland": 60.0, "MINISO Overseas": 30.0, "TOP TOY": 9.0, "Others": 1.0},
    }
    snapshot = {"currency": "RMB", "unit": "RMB millions", "periods": {"2026 H1": {"metrics": {"Revenue": 100.0}, "revenue_split": {"A": 100.0}}}}
    validate_refresh_payload(parsed, html, snapshot)

    parsed["period_end"] = "2026-03-31"
    with pytest.raises(SnapshotParseError):
        validate_refresh_payload(parsed, html, snapshot)

    parsed["period_end"] = "2026-06-30"
    parsed["revenue_split"]["Others"] = 2.0
    with pytest.raises(SnapshotParseError, match="does not reconcile"):
        validate_refresh_payload(parsed, html, snapshot)


def test_refresh_parser_fails_when_revenue_split_is_missing():
    fixture = """
    <html><body><table id='selected-financial-information'>
      <tr><th>Revenue</th><td>100</td></tr>
      <tr><th>Cost of sales</th><td>60</td></tr>
      <tr><th>Gross profit</th><td>40</td></tr>
      <tr><th>Operating profit</th><td>10</td></tr>
      <tr><th>Adjusted EBITDA</th><td>15</td></tr>
      <tr><th>Net cash from operating activities</th><td>12</td></tr>
      <tr><th>CAPEX</th><td>5</td></tr>
      <tr><th>Free cash flow</th><td>7</td></tr>
    </table></body></html>
    """
    with pytest.raises(SnapshotParseError, match="revenue split"):
        parse_public_html(fixture, "https://example.com/source", "2026-08-28")


@pytest.mark.parametrize("html", ["<html></html>", "<table><tr><td>Revenue</td><td>1</td></tr></table>"])
def test_refresh_parser_fails_loudly_when_structure_or_fields_change(html):
    with pytest.raises(SnapshotParseError):
        parse_public_html(html, "https://example.com/source", "2026-08-28")
