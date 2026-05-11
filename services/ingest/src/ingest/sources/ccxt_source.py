"""ccxt-based adapter — crypto.

Uses the exchange identifier from the asset's `source_symbol` of the form
`<exchange>:<symbol>` (e.g. `binance:BTC/USDT`). The exchange defaults
to Binance when unspecified.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import polars as pl
import structlog
from brokerapp_db import AssetClass, BarGranularity

from ingest.sources.base import (
    AssetLike,
    MarketDataSource,
    SourceNotSupportedError,
    SymbolUnknownError,
)

log = structlog.get_logger("ingest.ccxt")

_TIMEFRAME_MAP: dict[BarGranularity, str] = {
    BarGranularity.m5: "5m",
    BarGranularity.m15: "15m",
    BarGranularity.h1: "1h",
    BarGranularity.d1: "1d",
}

_BAR_MS: dict[BarGranularity, int] = {
    BarGranularity.m5: 5 * 60 * 1000,
    BarGranularity.m15: 15 * 60 * 1000,
    BarGranularity.h1: 60 * 60 * 1000,
    BarGranularity.d1: 24 * 60 * 60 * 1000,
}


class CCXTSource(MarketDataSource):
    name = "ccxt"

    def supports(self, asset_class: AssetClass) -> bool:
        return asset_class == AssetClass.crypto

    def fetch_bars(
        self,
        asset: AssetLike,
        granularity: BarGranularity,
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        if not self.supports(asset.asset_class):
            raise SourceNotSupportedError(
                f"ccxt does not support {asset.asset_class.value}.",
            )
        if granularity not in _TIMEFRAME_MAP:
            raise SourceNotSupportedError(f"ccxt has no mapping for {granularity}.")

        exchange_name, symbol = _split_symbol(asset)

        import ccxt  # noqa: PLC0415

        if not hasattr(ccxt, exchange_name):
            raise SymbolUnknownError(f"Unknown ccxt exchange {exchange_name!r}.")
        exchange_cls = getattr(ccxt, exchange_name)
        exchange = exchange_cls({"enableRateLimit": True})

        timeframe = _TIMEFRAME_MAP[granularity]
        since_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        step_ms = _BAR_MS[granularity]

        rows: list[list[float]] = []
        cursor = since_ms
        while cursor < end_ms:
            try:
                batch = exchange.fetch_ohlcv(
                    symbol,
                    timeframe=timeframe,
                    since=cursor,
                    limit=1000,
                )
            except ccxt.BadSymbol as exc:
                raise SymbolUnknownError(f"ccxt does not know {symbol!r}.") from exc

            if not batch:
                break
            rows.extend(batch)
            last = batch[-1][0]
            next_cursor = int(last) + step_ms
            if next_cursor <= cursor:
                # Defensive: guarantee progress so we never loop forever.
                break
            cursor = next_cursor

        if not rows:
            return _empty_frame()

        # ccxt returns [[time_ms, open, high, low, close, volume], ...]
        frame = pl.from_records(
            rows,
            schema=["time_ms", "open", "high", "low", "close", "volume"],
            orient="row",
        )
        frame = frame.with_columns(
            pl.col("time_ms").cast(pl.Int64).cast(pl.Datetime("ms", time_zone="UTC")).alias("time"),
        ).drop("time_ms")
        frame = frame.filter(
            pl.col("time")
            < datetime.fromtimestamp(end_ms / 1000, tz=datetime.now().astimezone().tzinfo)
        )  # filter overshoot

        return frame.with_columns(
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("adj_close"),
        ).select("time", "open", "high", "low", "close", "volume", "adj_close")


def _split_symbol(asset: AssetLike) -> tuple[str, str]:
    raw = asset.source_symbol or asset.symbol
    if ":" in raw:
        exchange, symbol = raw.split(":", 1)
        return exchange.strip().lower(), symbol.strip()
    return "binance", raw


def _empty_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema=[
            ("time", pl.Datetime(time_zone="UTC")),
            ("open", pl.Float64()),
            ("high", pl.Float64()),
            ("low", pl.Float64()),
            ("close", pl.Float64()),
            ("volume", pl.Float64()),
            ("adj_close", pl.Float64()),
        ],
    )


def _to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


__all__ = ["CCXTSource"]


# silence ruff
_ = log
