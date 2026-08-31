#!/usr/bin/env python3
"""Refresh the fixed public-data snapshot with explicit parser failures."""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/source/miniso_public_actuals.json"
SOURCE_URL = "https://ir.miniso.com/2026-08-28-MINISO-Group-Announces-2026-June-Quarter-and-Interim-Unaudited-Financial-Results"


class SnapshotParseError(ValueError):
    """Raised when the source no longer matches the expected table structure."""


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.current: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.in_row = True
            self.current = []
        elif self.in_row and tag in {"td", "th"}:
            self.in_cell = True

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "tr" and self.in_row:
            if self.current:
                self.rows.append(self.current)
            self.in_row = False
        elif tag in {"td", "th"}:
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell and self.in_row:
            text = " ".join(data.split())
            if text:
                self.current.append(text)


def parse_number(value: str) -> float:
    cleaned = value.replace(",", "").replace("RMB", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        raise SnapshotParseError(f"Expected numeric value, received: {value!r}")
    number = float(match.group(0))
    return -number if negative else number


def parse_h1_summary_value(cells: list[str]) -> float | None:
    """Return the 2026 H1 value from a 2025/H1/Q2 summary row."""
    candidates: list[float] = []
    for cell in cells:
        normalized = cell.strip()
        if "%" in normalized or re.fullmatch(r"\(\d+\)", normalized):
            continue
        try:
            candidates.append(parse_number(normalized))
        except SnapshotParseError:
            continue
    if not candidates:
        return None
    # The official summary table is 2025 H1, 2026 H1, Q2 2026, YoY.
    return candidates[1] if len(candidates) >= 2 else candidates[0]


def parse_public_html(html: str, source_url: str, source_date: str) -> dict:
    parser = TableParser()
    parser.feed(html)
    if not parser.rows:
        raise SnapshotParseError("No HTML table rows found; source page structure changed")
    aliases = {
        "Revenue": "Revenue", "Gross profit": "Gross Profit", "Gross Profit": "Gross Profit",
        "Operating profit": "Operating Profit", "Operating Profit": "Operating Profit",
        "Adjusted EBITDA": "Adjusted EBITDA", "Net cash from operating activities": "Operating Cash Flow",
        "Capital expenditure": "CAPEX", "CAPEX": "CAPEX", "Free cash flow": "FCF",
    }
    metrics: dict[str, float] = {}
    for row in parser.rows:
        if len(row) < 2:
            continue
        label = row[0].rstrip(":")
        for alias, metric in aliases.items():
            if label.lower().startswith(alias.lower()):
                value = parse_h1_summary_value(row[1:])
                if value is not None and metric not in metrics:
                    metrics[metric] = value
                break
    # The current IR release exposes operating cash flow, CAPEX, and FCF in
    # prose rather than in the selected-financial-information table. Keep the
    # table parser strict, but support those published sentences as a stable
    # fallback. The H1 paragraph precedes the Q2 paragraph on the source page,
    # so the first match is the H1 value used by this refresh job.
    plain_text = html_lib.unescape(re.sub(r"<[^>]+>", " ", html))
    plain_text = " ".join(plain_text.split())
    prose_patterns = {
        "Operating Cash Flow": r"Net cash from operating activities\s+was\s+RMB\s*([\d,]+(?:\.\d+)?)\s+million",
        "CAPEX": r"Capital expenditure\s+was\s+RMB\s*([\d,]+(?:\.\d+)?)\s+million",
        "FCF": r"free cash flow\s+was\s+RMB\s*([\d,]+(?:\.\d+)?)\s+million",
    }
    for metric, pattern in prose_patterns.items():
        if metric not in metrics:
            match = re.search(pattern, plain_text, flags=re.IGNORECASE)
            if match:
                metrics[metric] = parse_number(match.group(1))
    required = {"Revenue", "Gross Profit", "Operating Profit", "Adjusted EBITDA", "Operating Cash Flow", "CAPEX", "FCF"}
    missing = sorted(required - metrics.keys())
    if missing:
        raise SnapshotParseError(f"Missing required metrics after parsing: {', '.join(missing)}")
    return {"period_end": "2026-06-30", "source_url": source_url, "source_date": source_date, "provenance": "public_reported", "metrics": metrics}


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "PlanTerm/0.1 public snapshot refresh"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write parsed values to the committed snapshot")
    args = parser.parse_args()
    html = fetch(SOURCE_URL)
    parsed = parse_public_html(html, SOURCE_URL, "2026-08-28")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current = snapshot["periods"]["2026 H1"]
    print("Public snapshot differences (2026 H1):")
    changed = False
    for metric, value in parsed["metrics"].items():
        old = current["metrics"].get(metric)
        if old != value:
            changed = True
            print(f"- {metric}: {old} -> {value}")
    if not changed:
        print("- none")
    if args.write:
        current.update({key: parsed[key] for key in ("source_url", "source_date", "provenance")})
        current["metrics"].update(parsed["metrics"])
        SNAPSHOT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Updated {SNAPSHOT}")
    else:
        print("Dry-run only. Pass --write to update the snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
