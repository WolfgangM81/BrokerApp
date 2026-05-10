"""Idempotent bar upserts via Postgres `ON CONFLICT DO UPDATE`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog
from brokerapp_db import Bar
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ingest.convert import chunked

log = structlog.get_logger("ingest.repository")

UPSERT_BATCH = 1000


def upsert_bars(session: Session, rows: Sequence[dict[str, Any]]) -> int:
    """Insert / update bars by (asset_id, time, granularity).

    Returns the number of rows that were upserted (the union, not the
    distinction between inserts and updates — Postgres doesn't expose that
    cheaply without `xmax` tricks we don't need yet).
    """
    if not rows:
        return 0

    total = 0
    for batch in chunked(rows, UPSERT_BATCH):
        stmt = pg_insert(Bar).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Bar.asset_id, Bar.time, Bar.granularity],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "adj_close": stmt.excluded.adj_close,
                "source": stmt.excluded.source,
            },
        )
        session.execute(stmt)
        total += len(batch)
    log.info("bars_upserted", rows=total)
    return total
