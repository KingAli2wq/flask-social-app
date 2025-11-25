"""Database layer utilities for SQLAlchemy-backed persistence."""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import get_settings

# Load settings (DATABASE_URL and others come from env/.env)
settings = get_settings()

# Use the Pydantic settings value – this will read from .env
engine: Engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,
)

Base = declarative_base()


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine."""
    return engine


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """Alias for get_session used by some routers."""
    yield from get_session()


def create_session() -> Session:
    """Return a new SQLAlchemy session for background tasks or scripts."""
    return SessionLocal()


def init_db() -> None:
    """Initialise database schema by creating tables when missing."""
    # Import models to ensure they are registered on the metadata before create_all runs.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


__all__ = [
    "Base",
    "get_engine",
    "get_db",
    "get_session",
    "create_session",
    "init_db",
]