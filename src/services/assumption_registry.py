"""Deterministic assumption/build provenance without network or state writes."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from src.models.governance import AssumptionRegistry


_SAFE_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")
_SAFE_VERSION = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")


def current_git_sha(root: str | Path | None = None) -> str:
    """Use an explicit safe build value, then local git, then a documented fallback."""
    for key in ("PLANTERM_GIT_SHA", "PLANTERM_BUILD_GIT_SHA", "BUILD_GIT_SHA", "GIT_SHA", "SOURCE_VERSION"):
        value = os.getenv(key, "").strip()
        if _SAFE_SHA.fullmatch(value):
            return value.lower()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(root or Path(__file__).resolve().parents[2]),
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = result.stdout.strip()
        if _SAFE_SHA.fullmatch(value):
            return value.lower()
    except (OSError, subprocess.SubprocessError):
        pass
    return "working-tree"


def build_assumption_registry(case, *, root: str | Path | None = None) -> dict:
    canonical = json.dumps(case.assumptions, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    configured = os.getenv("PLANTERM_ASSUMPTION_VERSION", "").strip()
    version = configured if _SAFE_VERSION.fullmatch(configured) else f"{case.case_id}-assumptions-{digest}"
    registry = AssumptionRegistry(
        case_id=case.case_id,
        assumption_version=version,
        git_sha=current_git_sha(root),
        provenance_labels={str(key): str(value) for key, value in case.metadata.get("provenance_legend", {}).items()},
        as_of_date=case.metadata.get("as_of_date", "2026-06-30"),
    )
    return registry.model_dump(mode="json")


class AssumptionRegistryService:
    """Small stateless facade for callers that prefer a service object."""

    def __init__(self, *, root: str | Path | None = None):
        self.root = root

    def get(self, case) -> dict:
        return build_assumption_registry(case, root=self.root)


get_assumption_registry = build_assumption_registry
