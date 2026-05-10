"""Worker-side DB session for the forecast service."""

from __future__ import annotations

import os

from brokerapp_db import make_sync_engine, make_sync_sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def _url() -> str:
    user = os.environ.get("POSTGRES_USER", "brokerapp")
    pw = os.environ.get("POSTGRES_PASSWORD", "brokerapp")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "brokerapp")
    return f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{db}"


def get_session_factory() -> sessionmaker[Session]:
    global _engine, _factory
    if _factory is None:
        _engine = make_sync_engine(_url())
        _factory = make_sync_sessionmaker(_engine)
    return _factory
