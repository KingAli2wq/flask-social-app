"""
Runtime configuration helpers for the FastAPI application.

Correctly loads DATABASE_URL and other variables from the .env file
located in the project root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import EmailStr, Field
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
    public_base_url: str = Field(default="https://socialsphere.fly.dev", alias="PUBLIC_BASE_URL")

    email_host: str | None = Field(default=None, alias="EMAIL_HOST")
    email_port: int = Field(default=587, alias="EMAIL_PORT")
    email_username: str | None = Field(default=None, alias="EMAIL_USERNAME")
    email_password: str | None = Field(default=None, alias="EMAIL_PASSWORD")
    email_from_address: EmailStr | None = Field(default=None, alias="EMAIL_FROM_ADDRESS")
    email_use_tls: bool = Field(default=True, alias="EMAIL_USE_TLS")
    mailgun_api_key: str | None = Field(default=None, alias="MAILGUN_API_KEY")
    mailgun_domain: str | None = Field(default=None, alias="MAILGUN_DOMAIN")

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
