"""Pydantic schemas for API request/response bodies."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from brokerapp_db import AssetClass, BarGranularity
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    name: str | None = None
    asset_class: AssetClass
    exchange: str | None = None
    currency: str | None = None
    source: str
    calendar: str
    enabled: bool


class AssetCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    asset_class: AssetClass
    exchange: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    source: str = Field(min_length=1, max_length=32, default="yfinance")
    source_symbol: str | None = Field(default=None, max_length=64)
    calendar: str = Field(default="XNYS", max_length=16)


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------


class BarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: datetime
    granularity: BarGranularity
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    adj_close: Decimal | None = None
    source: str


class BarsResponse(BaseModel):
    asset_id: uuid.UUID
    granularity: BarGranularity
    bars: list[BarOut]


class BarUpsert(BaseModel):
    """Worker → API write payload (used in Phase 4 when we centralize writes;
    Phase 1 lets the worker write via SQLAlchemy directly)."""

    time: datetime
    granularity: BarGranularity
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    adj_close: Decimal | None = None
    source: str


# ---------------------------------------------------------------------------
# Watchlists
# ---------------------------------------------------------------------------


class WatchlistAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: uuid.UUID
    added_at: datetime


class WatchlistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class WatchlistDetail(WatchlistOut):
    members: list[WatchlistAssetOut] = Field(default_factory=list)


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)


class WatchlistMemberAdd(BaseModel):
    asset_id: uuid.UUID
