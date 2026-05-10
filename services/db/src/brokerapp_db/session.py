"""Engine + session factories.

Async (asyncpg) is exposed to the API; sync (psycopg) is exposed to the
worker. Both share the same models via this package; only the driver
differs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker


def make_async_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an asyncpg-backed engine. URL must start with `postgresql+asyncpg://`."""
    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
    )


def make_async_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def make_sync_engine(url: str, *, echo: bool = False) -> Engine:
    """Create a psycopg-backed engine. URL must start with `postgresql+psycopg://`."""
    return create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        future=True,
    )


def make_sync_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False, class_=Session)


@asynccontextmanager
async def async_session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Context manager that commits on success, rolls back on exception."""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Sync counterpart for the worker."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
