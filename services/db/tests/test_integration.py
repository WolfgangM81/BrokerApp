"""DB-level integration tests.

Skipped unless `BROKERAPP_DB_INTEGRATION_URL` points at a reachable
Postgres+TimescaleDB instance. CI's `generate:api-client` job is
configured to start a TimescaleDB service — extend it (or add a
dedicated `test:db` job) to drive these tests in pipelines.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from brokerapp_db import Asset, AssetClass, Bar, BarGranularity, User
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def test_extensions_and_schemas_present(migrated_db: Engine) -> None:
    with migrated_db.connect() as conn:
        ext = (
            conn.execute(
                text(
                    "SELECT extname FROM pg_extension WHERE extname IN ('timescaledb', 'pgcrypto')"
                ),
            )
            .scalars()
            .all()
        )
        schemas = (
            conn.execute(
                text("SELECT nspname FROM pg_namespace WHERE nspname IN ('app', 'market')"),
            )
            .scalars()
            .all()
        )
    assert {"timescaledb", "pgcrypto"} <= set(ext)
    assert {"app", "market"} == set(schemas)


def test_bars_is_hypertable(migrated_db: Engine) -> None:
    with migrated_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT hypertable_name FROM timescaledb_information.hypertables "
                "WHERE hypertable_schema = 'market' AND hypertable_name = 'bars'"
            ),
        ).first()
    assert row is not None, "market.bars must be a hypertable"


@pytest.fixture
def seed_user_and_asset(db_session: Session) -> tuple[User, Asset]:
    user = User(authentik_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4()}@test.local")
    asset = Asset(
        symbol="SPY",
        asset_class=AssetClass.etf,
        source="yfinance",
        calendar="XNYS",
    )
    db_session.add_all([user, asset])
    db_session.flush()
    return user, asset


def test_bar_upsert_is_idempotent(
    db_session: Session,
    seed_user_and_asset: tuple[User, Asset],
) -> None:
    _, asset = seed_user_and_asset
    when = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    base_row = {
        "asset_id": asset.id,
        "time": when,
        "granularity": BarGranularity.m5,
        "open": Decimal("100.0"),
        "high": Decimal("101.0"),
        "low": Decimal("99.0"),
        "close": Decimal("100.5"),
        "volume": Decimal("12345"),
        "adj_close": Decimal("100.5"),
        "source": "yfinance",
    }
    stmt = pg_insert(Bar).values(base_row)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Bar.asset_id, Bar.time, Bar.granularity],
        set_={"close": stmt.excluded.close},
    )
    db_session.execute(stmt)
    db_session.execute(stmt)  # second time — must be a no-op upsert
    db_session.flush()
    n = (
        db_session.execute(
            select(Bar).where(Bar.asset_id == asset.id, Bar.time == when),
        )
        .scalars()
        .all()
    )
    assert len(n) == 1


def test_bar_pk_blocks_duplicate_inserts(
    db_session: Session,
    seed_user_and_asset: tuple[User, Asset],
) -> None:
    _, asset = seed_user_and_asset
    bar1 = Bar(
        asset_id=asset.id,
        time=datetime(2026, 2, 1, tzinfo=UTC),
        granularity=BarGranularity.d1,
        open=Decimal("1.0"),
        high=Decimal("1.0"),
        low=Decimal("1.0"),
        close=Decimal("1.0"),
        volume=None,
        adj_close=None,
        source="yfinance",
    )
    db_session.add(bar1)
    db_session.flush()
    bar_dup = Bar(
        asset_id=asset.id,
        time=datetime(2026, 2, 1, tzinfo=UTC),
        granularity=BarGranularity.d1,
        open=Decimal("2.0"),
        high=Decimal("2.0"),
        low=Decimal("2.0"),
        close=Decimal("2.0"),
        volume=None,
        adj_close=None,
        source="yfinance",
    )
    db_session.add(bar_dup)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_asset_uniqueness_constraint(db_session: Session) -> None:
    db_session.add(Asset(symbol="AAPL", asset_class=AssetClass.stock, source="yfinance"))
    db_session.flush()
    db_session.add(Asset(symbol="AAPL", asset_class=AssetClass.stock, source="yfinance"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_continuous_query_range(
    db_session: Session,
    seed_user_and_asset: tuple[User, Asset],
) -> None:
    _, asset = seed_user_and_asset
    base = datetime(2026, 3, 1, tzinfo=UTC)
    bars = [
        Bar(
            asset_id=asset.id,
            time=base + timedelta(days=i),
            granularity=BarGranularity.d1,
            open=Decimal(str(100 + i)),
            high=Decimal(str(101 + i)),
            low=Decimal(str(99 + i)),
            close=Decimal(str(100 + i)),
            volume=None,
            adj_close=None,
            source="yfinance",
        )
        for i in range(5)
    ]
    db_session.add_all(bars)
    db_session.flush()
    rows = (
        db_session.execute(
            select(Bar).where(Bar.asset_id == asset.id).order_by(Bar.time),
        )
        .scalars()
        .all()
    )
    assert [r.time for r in rows] == [base + timedelta(days=i) for i in range(5)]
