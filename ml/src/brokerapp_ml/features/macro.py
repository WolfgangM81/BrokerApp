"""Macro features (Phase 5).

The fetcher uses FRED's anonymous CSV endpoint so no API key is needed
for the basic series. For higher rate limits, set `FRED_API_KEY` and
switch to the JSON endpoint in `_fetch_jsonl()`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx
import polars as pl

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Series we care about for daily-bar features. Keep this list narrow:
# every series adds an HTTP call and a join.
DEFAULT_SERIES: tuple[str, ...] = (
    "DFF",  # Effective Federal Funds Rate
    "VIXCLS",  # CBOE Volatility Index
    "DGS10",  # 10-year Treasury yield
    "DTWEXBGS",  # Trade-Weighted USD Index
)


def fetch_fred_series(
    series_id: str,
    *,
    start: datetime | None = None,
    timeout: float = 10.0,
) -> pl.DataFrame:
    """Return a Polars frame with `time` (UTC midnight) and the series values."""
    params: dict[str, str] = {"id": series_id}
    if start is not None:
        params["cosd"] = start.strftime("%Y-%m-%d")
    api_key = os.environ.get("FRED_API_KEY")
    if api_key:
        params["api_key"] = api_key
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(FRED_BASE, params=params)
    resp.raise_for_status()
    raw = resp.text
    return _csv_to_frame(raw, series_id)


def _csv_to_frame(text: str, series_id: str) -> pl.DataFrame:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return _empty(series_id)
    rows: list[tuple[datetime, float]] = []
    expected_cols = 2
    for line in lines[1:]:  # skip header
        parts = line.split(",")
        if len(parts) < expected_cols:
            continue
        try:
            day = datetime.strptime(parts[0], "%Y-%m-%d").replace(tzinfo=UTC)
            value = float(parts[1])
        except (ValueError, TypeError):
            continue
        rows.append((day, value))
    if not rows:
        return _empty(series_id)
    return pl.DataFrame(
        {"time": [r[0] for r in rows], series_id.lower(): [r[1] for r in rows]},
        schema_overrides={"time": pl.Datetime(time_zone="UTC")},
    )


def _empty(series_id: str) -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "time": pl.Datetime(time_zone="UTC"),
            series_id.lower(): pl.Float64,
        },
    )


def join_macro(
    bars: pl.DataFrame,
    macro: pl.DataFrame,
    *,
    on: str = "time",
) -> pl.DataFrame:
    """Forward-fill macro values onto bar timestamps (causal: t' <= t).

    Bars are typically intraday; macro is daily. We perform an as-of
    backward join so each bar gets the most recently observed macro
    value at-or-before its timestamp.
    """
    if macro.is_empty():
        return bars
    return bars.sort(on).join_asof(macro.sort(on), on=on, strategy="backward")


def build_macro_panel(
    series_ids: tuple[str, ...] = DEFAULT_SERIES,
    *,
    years: int = 5,
) -> pl.DataFrame:
    """Fetch all configured series, full-outer-join on date, forward-fill."""
    start = datetime.now(UTC) - timedelta(days=365 * years)
    panel: pl.DataFrame | None = None
    for sid in series_ids:
        frame = fetch_fred_series(sid, start=start)
        if frame.is_empty():
            continue
        panel = frame if panel is None else panel.join(frame, on="time", how="full", coalesce=True)
    if panel is None:
        return pl.DataFrame(schema={"time": pl.Datetime(time_zone="UTC")})
    return panel.sort("time").fill_null(strategy="forward")


__all__ = [
    "DEFAULT_SERIES",
    "build_macro_panel",
    "fetch_fred_series",
    "join_macro",
]
