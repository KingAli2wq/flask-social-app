"""Runtime configuration helpers for the FastAPI application.

The settings object centralises environment-dependent values, including the
DigitalOcean droplet IPv4 address. A default is provided so local development
continues to function if no overrides are supplied. Environment variables from
``.env`` are loaded eagerly to ensure values are available to both `os.getenv`
and Pydantic's settings model.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    """Typed application configuration sourced from environment variables."""

    droplet_host: str = Field(default="159.203.7.101", alias="DROPLET_HOST")
    app_name: str = Field(default="Social Backend", alias="APP_NAME")
    api_version: str = Field(default="0.1.0", alias="API_VERSION")

    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance.

    `lru_cache` avoids repeatedly parsing environment variables throughout the
    application's lifetime.
    """

    return Settings()


__all__ = ["Settings", "get_settings"]
