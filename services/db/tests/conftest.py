"""Shared DB fixtures.

These tests need a real Postgres with the TimescaleDB extension. They
are skipped by default; set `BROKERAPP_DB_INTEGRATION_URL` to a reachable
DSN (the CI's `timescale/timescaledb:2.17.0-pg16` service is the canonical
target) to run them.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

INTEGRATION_URL_ENV = "BROKERAPP_DB_INTEGRATION_URL"


def _integration_dsn() -> str | None:
    return os.environ.get(INTEGRATION_URL_ENV)


def _requires_dsn() -> str:
    dsn = _integration_dsn()
    if not dsn:
        pytest.skip(
            f"Set {INTEGRATION_URL_ENV} to a Postgres+Timescale DSN to "
            "run the DB integration tests.",
        )
    return dsn


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    dsn = _requires_dsn()
    engine = create_engine(dsn, future=True, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def migrated_db(db_engine: Engine) -> Iterator[Engine]:
    """Apply Alembic migrations once for the whole session."""
    from alembic import command
    from alembic.config import Config

    here = Path(__file__).resolve().parent.parent
    cfg = Config(str(here / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", str(db_engine.url))
    command.upgrade(cfg, "head")
    yield db_engine
    # We intentionally do not downgrade; CI databases are throwaway.


@pytest.fixture
def db_session(migrated_db: Engine) -> Iterator[Session]:
    """Per-test session wrapped in a transaction that always rolls back."""
    with migrated_db.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, future=True)
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture(autouse=True)
def _clear_app_tables(migrated_db: Engine) -> Iterator[None]:
    """Truncate non-time-series tables before each test for a clean slate."""
    yield
    with migrated_db.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE app.watchlist_assets, app.watchlists, "
                "app.trades, app.paper_portfolios, app.forecasts, "
                "app.backtests, app.models, app.assets, app.users "
                "RESTART IDENTITY CASCADE",
            ),
        )
        conn.execute(text("TRUNCATE TABLE market.bars"))
