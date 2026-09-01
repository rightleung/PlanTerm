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
    environment: str = "development"
    debug: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    case_dir: str = str(ROOT_DIR / "data" / "cases")
    snapshot_path: str = str(ROOT_DIR / "data" / "source" / "miniso_public_actuals.json")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
