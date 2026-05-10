"""Source registry — maps an Asset (by `source` field) to a MarketDataSource."""

from __future__ import annotations

from brokerapp_db import Asset

from ingest.sources.base import MarketDataSource, SourceNotSupportedError
from ingest.sources.ccxt_source import CCXTSource
from ingest.sources.yfinance_source import YFinanceSource

_REGISTRY: dict[str, MarketDataSource] = {
    "yfinance": YFinanceSource(),
    "ccxt": CCXTSource(),
}


def get_source(asset: Asset) -> MarketDataSource:
    source = _REGISTRY.get(asset.source)
    if source is None:
        raise SourceNotSupportedError(f"No adapter registered for source={asset.source!r}.")
    return source


__all__ = ["get_source"]
