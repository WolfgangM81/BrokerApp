"""Async DB engine + session factory wiring for the API.

The actual SQLAlchemy models live in `brokerapp_db` (services/db) and are
shared with the worker.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from brokerapp_db import (
    make_async_engine,
    make_async_sessionmaker,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from api.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_initialized(settings: Settings) -> None:
    global _engine, _session_factory
    if _engine is None:
        _engine = make_async_engine(settings.database_url)
        _session_factory = make_async_sessionmaker(_engine)


def get_engine() -> AsyncEngine:
    _ensure_initialized(get_settings())
    assert _engine is not None  # narrow for mypy
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    _ensure_initialized(get_settings())
    assert _session_factory is not None
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an `AsyncSession` per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Tear the engine down on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
