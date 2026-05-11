"""continuous aggregates + compression + retention

Revision ID: 0004_continuous_aggregates_and_compression
Revises: 0003_trade_journal_and_paper
Create Date: 2026-05-11 18:00:00.000000

Three TimescaleDB-native optimizations on `market.bars`:

1. **Continuous aggregates** for 15m / 1h / 1d derived from the 5m base.
   Stored as separate materialized views (`market.bars_15m`,
   `market.bars_1h`, `market.bars_1d`). The API picks the right view by
   requested granularity (see services/db/src/brokerapp_db/queries.py).

2. **Compression policy** — chunks older than 7 days are compressed in
   place. OHLCV compresses ~10-20×; on a 5-year intraday backfill that's
   ~10 GB -> ~700 MB.

3. **Retention policy** — drop 5m base chunks older than 2 years. The
   1d CAGG keeps the long-term picture; intraday detail beyond 2 years
   isn't useful for our forecast horizons (see ADR-0011 SLOs).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_continuous_aggregates_and_compression"
down_revision: str | Sequence[str] | None = "0003_trade_journal_and_paper"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Helper — emit one CAGG view + its refresh policy.
def _create_cagg(view_name: str, bucket: str, refresh_start: str, refresh_end: str) -> None:
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW market.{view_name}
        WITH (timescaledb.continuous) AS
        SELECT
            asset_id,
            time_bucket(INTERVAL '{bucket}', time) AS time,
            FIRST(open, time) AS open,
            MAX(high)          AS high,
            MIN(low)           AS low,
            LAST(close, time)  AS close,
            SUM(volume)        AS volume,
            LAST(adj_close, time) AS adj_close,
            FIRST(source, time)   AS source
        FROM market.bars
        WHERE granularity = '5m'
        GROUP BY asset_id, time_bucket(INTERVAL '{bucket}', time)
        WITH NO DATA;
        """,
    )
    op.execute(
        f"""
        SELECT add_continuous_aggregate_policy(
            'market.{view_name}',
            start_offset => INTERVAL '{refresh_start}',
            end_offset   => INTERVAL '{refresh_end}',
            schedule_interval => INTERVAL '15 minutes'
        );
        """,
    )


def upgrade() -> None:
    # --- Continuous aggregates ---------------------------------------
    # 15m: refresh covers the last 7 days, ending 5 min behind real-time.
    _create_cagg("bars_15m", "15 minutes", "7 days", "5 minutes")
    # 1h: refresh last 14 days.
    _create_cagg("bars_1h", "1 hour", "14 days", "30 minutes")
    # 1d (intraday→daily). Refresh the last 60 days; the DB also gets
    # explicit `granularity='1d'` rows from the EOD ingest, so this CAGG
    # is a fallback for assets where only intraday is available.
    _create_cagg("bars_1d_from_5m", "1 day", "60 days", "1 hour")

    # --- Compression policy ------------------------------------------
    op.execute(
        """
        ALTER TABLE market.bars
        SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'asset_id,granularity',
            timescaledb.compress_orderby   = 'time DESC'
        );
        """,
    )
    op.execute(
        """
        SELECT add_compression_policy(
            'market.bars',
            compress_after => INTERVAL '7 days'
        );
        """,
    )

    # --- Retention policy --------------------------------------------
    # Keep raw 5m bars for 2 years; CAGGs survive beyond that.
    # Daily bars (granularity='1d', stored directly) are unaffected by
    # this policy because the policy operates on the hypertable chunks,
    # not on a per-granularity basis. If we want to keep daily bars
    # indefinitely, we'd need to split daily into its own hypertable —
    # acceptable Phase-9 refactor.
    op.execute(
        """
        SELECT add_retention_policy(
            'market.bars',
            drop_after => INTERVAL '730 days'
        );
        """,
    )


def downgrade() -> None:
    op.execute("SELECT remove_retention_policy('market.bars', if_exists => TRUE);")
    op.execute("SELECT remove_compression_policy('market.bars', if_exists => TRUE);")
    op.execute("ALTER TABLE market.bars SET (timescaledb.compress = FALSE);")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market.bars_1d_from_5m CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market.bars_1h CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market.bars_15m CASCADE;")
