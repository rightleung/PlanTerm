"""Optional, explicitly allowlisted live public-data smoke test.

Ordinary deterministic CI never runs this module against the network.
"""

import asyncio
import os

import pytest

from src.models.public_import import Exchange, PublicImportRequest, Venue
from src.services.public_import.providers import default_providers
from src.services.public_import.service import preview_public_import


def _allowlist():
    entries = []
    for item in os.getenv("PLANTERM_PUBLIC_IMPORT_ALLOWLIST", "").split(","):
        parts = [part.strip() for part in item.split(":")]
        if len(parts) == 2:
            entries.append((parts[0], None, parts[1]))
        elif len(parts) == 3 and parts[0] == "A_SHARE":
            entries.append((parts[0], parts[1], parts[2]))
    return entries


@pytest.mark.skipif(os.getenv("PLANTERM_LIVE_PUBLIC_DATA") != "1", reason="live public-data smoke is opt-in")
def test_allowlisted_live_public_data_smoke():
    allowlist = _allowlist()
    if not allowlist:
        pytest.skip("PLANTERM_PUBLIC_IMPORT_ALLOWLIST is required")
    exchange, venue, ticker = allowlist[0]
    request = PublicImportRequest(exchange=Exchange(exchange), venue=Venue(venue) if venue else None, ticker=ticker)
    preview = asyncio.run(preview_public_import(request, providers=default_providers(True), rate_interval=0))
    assert preview.provenance.provider
    assert preview.request.normalized_symbol
    assert preview.provenance.retrieved_at
