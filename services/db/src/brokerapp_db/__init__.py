"""BrokerApp shared SQLAlchemy models and Alembic migrations.

This package is intentionally lean: it must be importable from both the
async API and the sync worker without dragging in FastAPI or Celery.
"""

from brokerapp_db.base import Base
from brokerapp_db.models import (
    Asset,
    AssetClass,
    Backtest,
    Bar,
    BarGranularity,
    Forecast,
    ForecastHorizon,
    Model,
    ModelStatus,
    PaperPortfolio,
    Trade,
    TradeSide,
    User,
    Watchlist,
    WatchlistAsset,
)
from brokerapp_db.queries import BarRow, fetch_bars
from brokerapp_db.session import (
    async_session_scope,
    make_async_engine,
    make_async_sessionmaker,
    make_sync_engine,
    make_sync_sessionmaker,
    session_scope,
)

__version__ = "0.1.0"

__all__ = [
    "Asset",
    "AssetClass",
    "Backtest",
    "Bar",
    "BarGranularity",
    "BarRow",
    "Base",
    "Forecast",
    "ForecastHorizon",
    "Model",
    "ModelStatus",
    "PaperPortfolio",
    "Trade",
    "TradeSide",
    "User",
    "Watchlist",
    "WatchlistAsset",
    "async_session_scope",
    "fetch_bars",
    "make_async_engine",
    "make_async_sessionmaker",
    "make_sync_engine",
    "make_sync_sessionmaker",
    "session_scope",
]
