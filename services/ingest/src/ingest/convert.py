"""Polars frame ⇄ DB rows.

Frames are our in-house format (ADR-0007); SQLAlchemy needs dict-shaped
rows for `INSERT ... ON CONFLICT DO UPDATE`.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

import polars as pl
from brokerapp_db import BarGranularity


def frame_to_bar_rows(
    frame: pl.DataFrame,
    *,
    asset_id: uuid.UUID,
    granularity: BarGranularity,
    source: str,
) -> list[dict[str, Any]]:
    """Convert a Polars OHLCV frame to dicts ready for SQLAlchemy upsert."""
    rows: list[dict[str, Any]] = []
    for record in frame.iter_rows(named=True):
        row = {
            "asset_id": asset_id,
            "time": record["time"],
            "granularity": granularity,
            "open": _to_decimal(record["open"]),
            "high": _to_decimal(record["high"]),
            "low": _to_decimal(record["low"]),
            "close": _to_decimal(record["close"]),
            "volume": _to_decimal(record.get("volume")),
            "adj_close": _to_decimal(record.get("adj_close")),
            "source": source,
        }
        if any(v is None for v in (row["open"], row["high"], row["low"], row["close"])):
            # Skip incomplete rows rather than violating NOT NULL constraints.
            continue
        rows.append(row)
    return rows


def _to_decimal(value: object) -> Decimal | None:  # noqa: PLR0911  exhaustive numeric dispatch
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    return None


def chunked(items: Iterable[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    """Yield successive lists of up to `size` items."""
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


__all__ = ["chunked", "frame_to_bar_rows"]
