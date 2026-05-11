"""Thin wrapper over `exchange_calendars` plus a synthetic 24/7 calendar
for crypto. Workers ask "is this market open right now?" before scheduling
intraday pulls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

import exchange_calendars as xcals
from brokerapp_db import AssetClass

# Crypto trades 24/7; we use a sentinel value so callers can branch.
CRYPTO_CALENDAR = "24/7"

_DEFAULT_PER_CLASS: dict[AssetClass, str] = {
    AssetClass.stock: "XNYS",
    AssetClass.etf: "XNYS",
    AssetClass.index: "XNYS",
    AssetClass.crypto: CRYPTO_CALENDAR,
    AssetClass.fx: CRYPTO_CALENDAR,  # FX is ~24/5 — treat as 24/7 for Phase 1
    AssetClass.commodity: "XNYS",
}


def default_calendar(asset_class: AssetClass) -> str:
    return _DEFAULT_PER_CLASS.get(asset_class, "XNYS")


@lru_cache(maxsize=16)
def _get_xcal(name: str) -> xcals.ExchangeCalendar:
    return xcals.get_calendar(name)


def is_market_open(calendar: str, when: datetime | None = None) -> bool:
    """Return True if the market identified by `calendar` is open at `when`.

    `when` defaults to now (UTC). The crypto sentinel always returns True.
    """
    if calendar == CRYPTO_CALENDAR:
        return True
    cal = _get_xcal(calendar)
    moment = when or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return bool(cal.is_trading_minute(moment.astimezone(UTC)))


__all__ = ["CRYPTO_CALENDAR", "default_calendar", "is_market_open"]
