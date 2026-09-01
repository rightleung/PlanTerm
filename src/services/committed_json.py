"""Fail-closed JSON loading for committed case artifacts and request payloads."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DuplicateJsonKeyError(ValueError):
    """Raised when a JSON object repeats a key at any nesting level."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_json(value: str | bytes | bytearray) -> Any:
    """Parse JSON without silently accepting duplicate object keys."""
    return json.loads(value, object_pairs_hook=_reject_duplicate_keys)


def load_committed_json(path: str | Path) -> Any:
    """Load a committed JSON artifact and reject ambiguous duplicate keys."""
    return loads_json(Path(path).read_text(encoding="utf-8"))
