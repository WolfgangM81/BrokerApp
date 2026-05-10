"""Calendar wrapper tests — covers the synthetic 24/7 path."""

from __future__ import annotations

from datetime import datetime

from brokerapp_db import AssetClass
from ingest.calendars import (
    CRYPTO_CALENDAR,
    default_calendar,
    is_market_open,
)


def test_default_calendar_per_class() -> None:
    assert default_calendar(AssetClass.stock) == "XNYS"
    assert default_calendar(AssetClass.etf) == "XNYS"
    assert default_calendar(AssetClass.crypto) == CRYPTO_CALENDAR
    assert default_calendar(AssetClass.fx) == CRYPTO_CALENDAR


def test_crypto_calendar_is_always_open() -> None:
    assert is_market_open(CRYPTO_CALENDAR) is True
    # Christmas day, 03:00 UTC — still open for crypto.
    assert is_market_open(CRYPTO_CALENDAR, datetime(2025, 12, 25, 3, 0, 0)) is True
