"""Frame → row conversion + chunking."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import polars as pl
from brokerapp_db import BarGranularity
from ingest.convert import chunked, frame_to_bar_rows


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "time": [
                datetime(2026, 1, 2, 14, 30, tzinfo=UTC),
                datetime(2026, 1, 2, 14, 35, tzinfo=UTC),
                datetime(2026, 1, 2, 14, 40, tzinfo=UTC),
            ],
            "open": [100.0, 101.0, math.nan],
            "high": [101.0, 102.0, 103.0],
            "low": [99.5, 100.5, 102.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000.0, 2000.0, 3000.0],
            "adj_close": [100.5, 101.5, 102.5],
        },
        schema_overrides={"time": pl.Datetime(time_zone="UTC")},
    )


def test_frame_to_bar_rows_basic() -> None:
    asset_id = uuid.uuid4()
    rows = frame_to_bar_rows(
        _frame(),
        asset_id=asset_id,
        granularity=BarGranularity.m5,
        source="yfinance",
    )
    # Third row has NaN open → skipped.
    assert len(rows) == 2
    first = rows[0]
    assert first["asset_id"] == asset_id
    assert first["granularity"] is BarGranularity.m5
    assert first["source"] == "yfinance"
    assert first["open"] == Decimal("100.0")
    assert first["close"] == Decimal("100.5")
    assert first["volume"] == Decimal("1000.0")


def test_empty_frame_yields_empty_rows() -> None:
    empty = pl.DataFrame(
        schema={
            "time": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
            "adj_close": pl.Float64,
        },
    )
    rows = frame_to_bar_rows(
        empty,
        asset_id=uuid.uuid4(),
        granularity=BarGranularity.d1,
        source="yfinance",
    )
    assert rows == []


def test_chunked() -> None:
    items = [{"i": i} for i in range(7)]
    batches = list(chunked(items, 3))
    assert [len(b) for b in batches] == [3, 3, 1]
    assert sum(len(b) for b in batches) == 7
