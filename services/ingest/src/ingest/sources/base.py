"""MarketDataSource — abstract adapter contract.

Adapters are responsible for:
- Mapping our `Asset` row to whatever symbol shape the source expects.
- Fetching OHLCV bars for a window at a given granularity.
- Returning **UTC** timestamps and Polars frames (ADR-0007). Adapters
  convert pandas/source-specific frames internally; nothing pandas-shaped
  leaves the adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

import polars as pl
from brokerapp_db import AssetClass, BarGranularity


class SourceError(Exception):
    """Base class for source-adapter errors."""


class SymbolUnknownError(SourceError):
    """The adapter could not resolve the requested symbol."""


class SourceNotSupportedError(SourceError):
    """The adapter does not support the requested asset class / granularity."""


@dataclass(frozen=True, slots=True)
class Bar:
    """In-flight bar representation. Decimals preserve OHLC precision."""

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    adj_close: Decimal | None


class AssetLike(Protocol):
    """Minimum shape an adapter needs from an Asset."""

    symbol: str
    source_symbol: str | None
    asset_class: AssetClass


class MarketDataSource(ABC):
    """Adapter interface. One instance per source (yfinance, ccxt, ...)."""

    name: str

    @abstractmethod
    def supports(self, asset_class: AssetClass) -> bool:
        """Return whether this source can serve the given asset class."""

    @abstractmethod
    def fetch_bars(
        self,
        asset: AssetLike,
        granularity: BarGranularity,
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """Return a Polars frame with columns:

            time (datetime, UTC), open, high, low, close, volume, adj_close

        Frame may be empty if no bars are available in the requested window.
        Adapters must raise `SymbolUnknownError` rather than returning an empty
        frame if the symbol does not exist at all.
        """


__all__ = [
    "AssetLike",
    "Bar",
    "MarketDataSource",
    "SourceError",
    "SourceNotSupportedError",
    "SymbolUnknownError",
]
