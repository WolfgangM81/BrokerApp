# Celery decorators are untyped (return Any); mypy strict would force
# every task to spell out `(self: Any) -> Any` and still complain about
# `@celery_app.task`. Disable the two relevant codes file-wide.
# mypy: disable-error-code="untyped-decorator,no-untyped-def"
"""Celery tasks for the ingest worker.

Phase 1 tasks:
- ingest.ping              — smoke test
- ingest.backfill_asset    — full N-year history fetch for a newly-added asset
- ingest.refresh_asset     — incremental refresh (last K days) for one asset
- ingest.refresh_universe  — fan-out: refresh every enabled, watched asset

All bar writes go through `upsert_bars` so re-runs are idempotent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from brokerapp_db import Asset, BarGranularity, WatchlistAsset, session_scope
from sqlalchemy import select

from ingest.calendars import is_market_open
from ingest.celery_app import celery_app
from ingest.convert import frame_to_bar_rows
from ingest.db import get_session_factory
from ingest.repository import upsert_bars
from ingest.sources.base import SourceError
from ingest.sources.registry import get_source

log = structlog.get_logger("ingest.tasks")

# Granularities ingested on every refresh cycle. 5m is intraday, 1d is EOD.
DEFAULT_GRANULARITIES: tuple[BarGranularity, ...] = (
    BarGranularity.m5,
    BarGranularity.d1,
)


@celery_app.task(name="ingest.ping")
def ping() -> dict[str, str]:
    """Smoke-test task — used by health checks during the skeleton phase."""
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


@celery_app.task(name="ingest.backfill_asset", bind=True, max_retries=3)
def backfill_asset(self, asset_id: str, years: int = 5) -> dict[str, int]:
    """Pull `years` of history for `asset_id` across default granularities."""
    end = datetime.now(UTC)
    start = end - timedelta(days=365 * years)
    log.info("backfill_start", asset_id=asset_id, years=years, start=start.isoformat())

    rows_total = 0
    factory = get_session_factory()
    with session_scope(factory) as session:
        asset = session.get(Asset, uuid.UUID(asset_id))
        if asset is None:
            log.warning("backfill_asset_missing", asset_id=asset_id)
            return {"rows": 0}
        source = get_source(asset)
        for gran in DEFAULT_GRANULARITIES:
            if not source.supports(asset.asset_class):
                continue
            try:
                frame = source.fetch_bars(asset, gran, start, end)
            except SourceError as exc:
                log.warning(
                    "backfill_source_error",
                    asset_id=asset_id,
                    granularity=gran.value,
                    error=str(exc),
                )
                continue
            rows = frame_to_bar_rows(
                frame,
                asset_id=asset.id,
                granularity=gran,
                source=source.name,
            )
            rows_total += upsert_bars(session, rows)
    log.info("backfill_done", asset_id=asset_id, rows=rows_total)
    return {"rows": rows_total}


@celery_app.task(name="ingest.refresh_asset", bind=True, max_retries=3)
def refresh_asset(self, asset_id: str, days: int = 7) -> dict[str, int]:
    """Pull the last `days` of bars for `asset_id`. Cheap, run frequently."""
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    rows_total = 0
    factory = get_session_factory()
    with session_scope(factory) as session:
        asset = session.get(Asset, uuid.UUID(asset_id))
        if asset is None or not asset.enabled:
            return {"rows": 0}
        source = get_source(asset)
        for gran in DEFAULT_GRANULARITIES:
            if not source.supports(asset.asset_class):
                continue
            # For intraday granularities, skip if the market is closed and
            # there can't be new bars yet.
            intraday = gran in {BarGranularity.m5, BarGranularity.m15, BarGranularity.h1}
            if intraday and not is_market_open(asset.calendar):
                continue
            try:
                frame = source.fetch_bars(asset, gran, start, end)
            except SourceError as exc:
                log.warning("refresh_source_error", asset_id=asset_id, error=str(exc))
                continue
            rows = frame_to_bar_rows(
                frame,
                asset_id=asset.id,
                granularity=gran,
                source=source.name,
            )
            rows_total += upsert_bars(session, rows)
    return {"rows": rows_total}


@celery_app.task(name="ingest.refresh_universe")
def refresh_universe(days: int = 2) -> dict[str, int]:
    """Refresh every asset that is on at least one watchlist."""
    factory = get_session_factory()
    with session_scope(factory) as session:
        stmt = (
            select(Asset.id)
            .join(WatchlistAsset, WatchlistAsset.asset_id == Asset.id)
            .where(Asset.enabled.is_(True))
            .distinct()
        )
        asset_ids = [row[0] for row in session.execute(stmt).all()]

    log.info("refresh_universe_dispatch", n=len(asset_ids), days=days)
    for asset_id in asset_ids:
        refresh_asset.apply_async(args=[str(asset_id), days], queue="ingest")
    return {"dispatched": len(asset_ids)}
