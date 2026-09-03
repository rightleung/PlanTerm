from __future__ import annotations
import json
from pathlib import Path
from .providers import FixtureProvider, ProviderResult

def fixture_provider() -> FixtureProvider:
    fixture_dir = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "public_import"
    fixture_files = ("us_aapl.json", "lse_vod.json", "hkex_0005.json", "sse_600519.json", "szse_000001.json")
    fixtures = {}
    for filename in fixture_files:
        payload = json.loads((fixture_dir / filename).read_text())
        key = f"{payload['exchange']}:{payload.get('venue', '')}:{payload['normalized_symbol']}"
        fixtures[key] = ProviderResult(payload["company"], payload["statements"], payload["source_url"])
    return FixtureProvider(fixtures)
