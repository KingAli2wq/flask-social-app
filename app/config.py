"""
Runtime configuration helpers for the FastAPI application.

Correctly loads DATABASE_URL and other variables from the .env file
located in the project root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the project root
BASE_DIR = Path(__file__).resolve().parents[1]

# Absolute path to .env
ENV_PATH = BASE_DIR / ".env"

# Load .env defaults without overriding environment variables provided by the platform
load_dotenv(dotenv_path=ENV_PATH, override=False)


class Settings(BaseSettings):
    # Required field — must come from .env
    database_url: str = Field(..., alias="DATABASE_URL")

    # Optional fields
    droplet_host: str = Field(default="159.203.7.101", alias="DROPLET_HOST")
    app_name: str = Field(default="Social Backend", alias="APP_NAME")
    api_version: str = Field(default="0.1.0", alias="API_VERSION")

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
