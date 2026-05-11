"""Read-side helpers that know about TimescaleDB-specific structures.

The bars endpoint takes a `granularity` parameter and we want to serve it
from the most efficient source:

- `5m` and `1d` come straight from `market.bars` (rows stored at that
  granularity by the ingest worker).
- `15m`, `1h` come from continuous aggregates created in migration 0004.

This module is the only place where the routing decision lives so the
API route stays small and the worker doesn't have to care about it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from brokerapp_db.models import BarGranularity


class BarRow(TypedDict):
    """Shape that matches the API's `BarOut` schema."""

    time: datetime
    granularity: BarGranularity
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    adj_close: Decimal | None
    source: str


# Granularities that have a dedicated CAGG view (Migration 0004).
_CAGG_TABLES: dict[BarGranularity, str] = {
    BarGranularity.m15: "market.bars_15m",
    BarGranularity.h1: "market.bars_1h",
}


def _is_cagg(granularity: BarGranularity) -> bool:
    return granularity in _CAGG_TABLES


async def fetch_bars(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    granularity: BarGranularity,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list[BarRow]:
    """Read bars at the requested granularity, choosing CAGG vs base table."""
    if _is_cagg(granularity):
        view = _CAGG_TABLES[granularity]
        # `view` is a closed-set lookup from a literal dict — no user
        # input ever reaches the f-string. Silence the S608 lint here.
        # CAGG views don't carry the `granularity` column — we synthesize it.
        query = f"""
            SELECT
                time,
                :granularity AS granularity,
                open, high, low, close,
                volume, adj_close, source
            FROM {view}
            WHERE asset_id = :asset_id
              AND (:start IS NULL OR time >= :start)
              AND (:end   IS NULL OR time <  :end)
            ORDER BY time ASC
            LIMIT :limit
            """  # noqa: S608  closed-set table name, not user input
        sql = text(query)
    else:
        sql = text(
            """
            SELECT
                time,
                granularity,
                open, high, low, close,
                volume, adj_close, source
            FROM market.bars
            WHERE asset_id    = :asset_id
              AND granularity = :granularity
              AND (:start IS NULL OR time >= :start)
              AND (:end   IS NULL OR time <  :end)
            ORDER BY time ASC
            LIMIT :limit
            """,
        )

    result = await session.execute(
        sql,
        {
            "asset_id": asset_id,
            "granularity": granularity.value,
            "start": start,
            "end": end,
            "limit": limit,
        },
    )
    rows = result.mappings().all()
    return [
        BarRow(
            time=r["time"],
            granularity=BarGranularity(r["granularity"]),
            open=Decimal(str(r["open"])),
            high=Decimal(str(r["high"])),
            low=Decimal(str(r["low"])),
            close=Decimal(str(r["close"])),
            volume=Decimal(str(r["volume"])) if r["volume"] is not None else None,
            adj_close=Decimal(str(r["adj_close"])) if r["adj_close"] is not None else None,
            source=r["source"],
        )
        for r in rows
    ]


__all__ = ["BarRow", "fetch_bars"]
