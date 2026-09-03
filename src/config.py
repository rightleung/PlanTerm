"""Centralized runtime settings for PlanTerm."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PlanTerm"
    app_port: int = Field(8000, ge=1, le=65535)
    version: str = "0.2.0"
    # Additive release contract for v1.1 review; keep the legacy package/API
    # version until the release owner approves the metadata transition.
    release_id: str = "1.1.0-rc.1"
    environment: str = "development"
    debug: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    case_dir: str = str(ROOT_DIR / "data" / "cases")
    snapshot_path: str = str(ROOT_DIR / "data" / "source" / "miniso_public_actuals.json")
    public_import_enabled: bool = False
    public_import_live_enabled: bool = False
    public_import_workers: int = Field(4, ge=1, le=32)
    public_import_provider_timeout_seconds: float = Field(8.0, gt=0, le=30)
    public_import_deadline_seconds: float = Field(12.0, gt=0, le=60)
    public_import_retry_count: int = Field(2, ge=0, le=2)
    public_import_rate_limit_seconds: float = Field(1.0, ge=0, le=60)
    public_import_cache_size: int = Field(256, ge=1, le=4096)
    public_import_cache_ttl_seconds: int = Field(900, ge=1, le=86400)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
