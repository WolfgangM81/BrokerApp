"""Domain models.

All times stored in UTC (see ADR-0011). Bars are partitioned via a
TimescaleDB hypertable created by the initial migration's post-processing
hook (see ADR-0001 + migrations/env.py).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from brokerapp_db.base import Base, utcnow


class AssetClass(enum.StrEnum):
    """Top-level asset taxonomy. Drives ingest adapter selection + calendar."""

    stock = "stock"
    etf = "etf"
    index = "index"
    crypto = "crypto"
    fx = "fx"
    commodity = "commodity"


class BarGranularity(enum.StrEnum):
    """Bar granularity. The hypertable stores 5m as base; longer bars are
    served via continuous aggregates added in a later migration."""

    m5 = "5m"
    m15 = "15m"
    h1 = "1h"
    d1 = "1d"


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    authentik_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    base_currency: Mapped[str] = mapped_column(String(3), default="EUR")
    locale: Mapped[str] = mapped_column(String(8), default="de")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    watchlists: Mapped[list[Watchlist]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# assets
# ---------------------------------------------------------------------------


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "asset_class",
            "source",
            name="uq_assets_symbol_class_source",
        ),
        Index("ix_assets_asset_class", "asset_class"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    asset_class: Mapped[AssetClass] = mapped_column(Enum(AssetClass, name="asset_class"))
    exchange: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str | None] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(32))  # yfinance / ccxt / ...
    source_symbol: Mapped[str | None] = mapped_column(String(64))
    # Calendar identifier accepted by exchange_calendars (e.g. "XNYS",
    # "XETR", "24/7" for crypto).
    calendar: Mapped[str] = mapped_column(String(16), default="XNYS")
    enabled: Mapped[bool] = mapped_column(default=True)
    extra: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
# bars (hypertable — see migration)
# ---------------------------------------------------------------------------


class Bar(Base):
    __tablename__ = "bars"
    __table_args__ = (
        # Composite PK: (asset_id, time, granularity). Hypertable partition
        # column is `time`; uniqueness enforces idempotent ingest.
        UniqueConstraint(
            "asset_id",
            "time",
            "granularity",
            name="uq_bars_asset_time_granularity",
        ),
        Index("ix_bars_asset_time", "asset_id", "time"),
        # Bars live in the `market` schema so they can be backed up / pruned
        # independently from app metadata. The `info["timescale"]` block is
        # consumed by migrations/env.py to emit `create_hypertable(...)`.
        {
            "schema": "market",
            "info": {
                "timescale": {
                    "hypertable": {
                        "time_column_name": "time",
                        "chunk_time_interval": "INTERVAL '7 days'",
                    },
                },
            },
        },
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    time: Mapped[datetime] = mapped_column(primary_key=True)
    granularity: Mapped[BarGranularity] = mapped_column(
        Enum(BarGranularity, name="bar_granularity"),
        primary_key=True,
    )
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(28, 8))
    # Adjusted close (split/dividend-aware) where the source provides it.
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    # Source attribution per row to support multi-source reconciliation.
    source: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---------------------------------------------------------------------------
# watchlists
# ---------------------------------------------------------------------------


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(back_populates="watchlists")
    members: Mapped[list[WatchlistAsset]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
    )


class WatchlistAsset(Base):
    __tablename__ = "watchlist_assets"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id",
            "asset_id",
            name="uq_watchlist_assets_watchlist_asset",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.watchlists.id", ondelete="CASCADE"),
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.assets.id", ondelete="CASCADE"),
        index=True,
    )
    added_at: Mapped[datetime] = mapped_column(default=utcnow)

    watchlist: Mapped[Watchlist] = relationship(back_populates="members")


# ---------------------------------------------------------------------------
# Forecasts and backtests (Phase 3+)
# ---------------------------------------------------------------------------


class ForecastHorizon(enum.StrEnum):
    """Multi-horizon forecast outputs returned together by global models."""

    h1 = "1h"
    d1 = "1d"
    d5 = "5d"
    d20 = "20d"


class ModelStatus(enum.StrEnum):
    staging = "staging"
    production = "production"
    archived = "archived"


class Model(Base):
    """Registry record for a trained model artifact (full artifact lives in
    MLflow / MinIO; this row tracks the metadata visible to the API)."""

    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_models_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(64))  # 'naive', 'arima', 'lightgbm', ...
    version: Mapped[str] = mapped_column(String(64))  # MLflow run id
    asset_class: Mapped[AssetClass | None] = mapped_column(
        Enum(AssetClass, name="asset_class"),
        nullable=True,
    )
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus, name="model_status"),
        default=ModelStatus.staging,
    )
    mlflow_uri: Mapped[str | None] = mapped_column(String(255))
    metrics: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    feature_schema: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Forecast(Base):
    """One stored forecast for one (asset, horizon, model, as_of) tuple.

    `value` is the point estimate; `quantiles` carries q10/q50/q90 for
    confidence-band UIs.
    """

    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "model_id",
            "as_of",
            "horizon",
            name="uq_forecasts_asset_model_asof_horizon",
        ),
        Index("ix_forecasts_asset_asof", "asset_id", "as_of"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.assets.id", ondelete="CASCADE"),
        index=True,
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.models.id", ondelete="CASCADE"),
        index=True,
    )
    as_of: Mapped[datetime] = mapped_column()  # the t at which the forecast was made
    horizon: Mapped[ForecastHorizon] = mapped_column(
        Enum(ForecastHorizon, name="forecast_horizon"),
    )
    target_time: Mapped[datetime] = mapped_column()  # t + horizon
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    quantiles: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    explain: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Backtest(Base):
    """Result of a walk-forward backtest run."""

    __tablename__ = "backtests"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.assets.id", ondelete="CASCADE"),
        index=True,
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.models.id", ondelete="CASCADE"),
        index=True,
    )
    horizon: Mapped[ForecastHorizon] = mapped_column(
        Enum(ForecastHorizon, name="forecast_horizon"),
    )
    train_start: Mapped[datetime] = mapped_column()
    train_end: Mapped[datetime] = mapped_column()
    test_start: Mapped[datetime] = mapped_column()
    test_end: Mapped[datetime] = mapped_column()
    metrics: Mapped[dict[str, float]] = mapped_column(JSONB)
    config: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---------------------------------------------------------------------------
# Trade journal + paper portfolios (Phase 4+)
# ---------------------------------------------------------------------------


class TradeSide(enum.StrEnum):
    buy = "buy"
    sell = "sell"


class Trade(Base):
    """Manual trade-journal entry (real or paper).

    Real trades let users compare model recommendations against their own
    decisions; paper trades are populated by the paper-portfolio simulator
    in Phase 6 and have `paper=True`.
    """

    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.users.id", ondelete="CASCADE"),
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.assets.id", ondelete="CASCADE"),
        index=True,
    )
    side: Mapped[TradeSide] = mapped_column(Enum(TradeSide, name="trade_side"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    traded_at: Mapped[datetime] = mapped_column()
    notes: Mapped[str | None] = mapped_column(String(2048))
    paper: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_paper_portfolios_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("app.users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64))
    base_currency: Mapped[str] = mapped_column(String(3), default="EUR")
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    strategy: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
