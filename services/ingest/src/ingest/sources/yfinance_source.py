"""yfinance-based adapter — stocks, ETFs, indices.

Caveats baked into Phase 1:
- 1m / 5m bars are only available for the last 60 days (Yahoo limit).
- We always pull adjusted-close where available.
- yfinance returns pandas; we convert at the boundary to Polars (ADR-0007).
"""

from __future__ import annotations

from datetime import datetime, timezone
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

log = structlog.get_logger("ingest.yfinance")

_INTERVAL_MAP: dict[BarGranularity, str] = {
    BarGranularity.m5: "5m",
    BarGranularity.m15: "15m",
    BarGranularity.h1: "60m",
    BarGranularity.d1: "1d",
}

_SUPPORTED: set[AssetClass] = {
    AssetClass.stock,
    AssetClass.etf,
    AssetClass.index,
}


class YFinanceSource(MarketDataSource):
    name = "yfinance"

    def supports(self, asset_class: AssetClass) -> bool:
        return asset_class in _SUPPORTED

    def fetch_bars(
        self,
        asset: AssetLike,
        granularity: BarGranularity,
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        if not self.supports(asset.asset_class):
            raise SourceNotSupportedError(
                f"yfinance does not support {asset.asset_class.value}.",
            )
        if granularity not in _INTERVAL_MAP:
            raise SourceNotSupportedError(f"yfinance has no mapping for {granularity}.")

        # Imported lazily so unit tests can run without yfinance available.
        import yfinance as yf  # noqa: PLC0415

        symbol = asset.source_symbol or asset.symbol
        log.info(
            "fetch_bars",
            symbol=symbol,
            granularity=granularity.value,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        ticker = yf.Ticker(symbol)
        # yfinance accepts naive datetimes and treats them as UTC for the
        # daily endpoint; for intraday endpoints it wants tz-aware.
        df_pandas = ticker.history(
            start=start,
            end=end,
            interval=_INTERVAL_MAP[granularity],
            auto_adjust=False,
            prepost=False,
            actions=False,
        )

        if df_pandas is None or df_pandas.empty:
            # Probe info to decide between empty-window vs unknown symbol.
            try:
                info = ticker.info  # may hit the network
            except Exception:
                info = None
            if not info or info.get("regularMarketPrice") is None:
                raise SymbolUnknownError(f"yfinance has no data for {symbol!r}.")
            return _empty_frame()

        # Normalize: ensure UTC tz-aware index, then to Polars.
        df_pandas.index = df_pandas.index.tz_convert("UTC")
        df_pandas = df_pandas.reset_index().rename(
            columns={
                "Datetime": "time",
                "Date": "time",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
                "Adj Close": "adj_close",
            },
        )

        frame = pl.from_pandas(
            df_pandas[["time", "open", "high", "low", "close", "volume", "adj_close"]]
            if "adj_close" in df_pandas.columns
            else df_pandas[["time", "open", "high", "low", "close", "volume"]]
        )
        return _coerce_frame(frame)


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


def _coerce_frame(frame: pl.DataFrame) -> pl.DataFrame:
    columns = frame.columns
    if "adj_close" not in columns:
        frame = frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("adj_close"))
    return frame.with_columns(
        pl.col("time").cast(pl.Datetime(time_zone="UTC")),
        pl.col("open").cast(pl.Float64),
        pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64),
        pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
        pl.col("adj_close").cast(pl.Float64),
    )


def _to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


__all__ = ["YFinanceSource"]


# Silence ruff about unused imports we keep for module typing.
_ = timezone
