"""Worker-side DB plumbing (sync psycopg)."""

from __future__ import annotations

from brokerapp_db import make_sync_engine, make_sync_sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ingest.config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        settings = get_settings()
        _engine = make_sync_engine(settings.sync_database_url)
        _factory = make_sync_sessionmaker(_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _factory
    if _factory is None:
        get_engine()
    assert _factory is not None
    return _factory


def dispose_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
