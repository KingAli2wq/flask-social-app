"""Helpers for running Alembic migrations at runtime.

Some deployment targets (including certain PaaS platforms) do not reliably execute
Procfile `release` commands. When that happens, the app code can get ahead of the
database schema.

This module provides an opt-out, best-effort migration runner that can be invoked
from FastAPI startup.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path


logger = logging.getLogger(__name__)


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_VALUES


def _should_run_migrations(database_url: str) -> bool:
    # Keep tests hermetic.
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return False

    # Allow operators to opt-out.
    if _is_truthy(os.getenv("DISABLE_AUTO_MIGRATIONS")):
        return False

    # Allow operators to opt-in explicitly (overrides URL checks).
    if _is_truthy(os.getenv("AUTO_MIGRATE")):
        return True

    # Default behavior: run migrations for non-sqlite URLs.
    if database_url.strip().lower().startswith("sqlite"):
        return False

    return True


def run_migrations_if_needed(*, database_url: str) -> bool:
    """Run `alembic upgrade head` if enabled.

    Returns True if migrations were attempted (regardless of success).
    """

    if not _should_run_migrations(database_url):
        logger.info("Auto-migrations disabled")
        return False

    from alembic import command
    from alembic.config import Config

    repo_root = Path(__file__).resolve().parents[2]
    alembic_ini = repo_root / "alembic.ini"

    if not alembic_ini.exists():
        logger.warning("Auto-migrations skipped: missing alembic.ini at %s", alembic_ini)
        return False

    logger.info("Running Alembic migrations (upgrade head)")

    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", database_url)

    # Ensure `script_location` resolves when the CWD isn't the repo root.
    config.set_main_option("script_location", str(repo_root / "alembic"))

    # With our merge revision, `head` is unambiguous.
    command.upgrade(config, "head")
    logger.info("Alembic migrations completed")
    return True
