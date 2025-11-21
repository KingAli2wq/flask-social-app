"""
Runtime configuration helpers for the FastAPI application.

This version correctly loads DATABASE_URL from the project root .env file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the project's root directory
BASE_DIR = Path(__file__).resolve().parents[1]

# Absolute path to .env
ENV_PATH = BASE_DIR / ".env"

# Load .env before creating settings
load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    """Typed application configuration sourced from environment variables."""

    # REQUIRED – loaded from .env
    database_url: str = Field(alias="DATABASE_URL")

    # Optional general settings
    droplet_host: str = Field(default="159.203.7.101", alias="DROPLET_HOST")
    app_name: str = Field(default="Social Backend", alias="APP_NAME")
    api_version: str = Field(default="0.1.0", alias="API_VERSION")

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


__all__ = ["Settings", "get_settings"]
