"""initial schema: users, assets, bars (hypertable), watchlists

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-10 18:00:00.000000

This is the only hand-written migration: it bootstraps the schemas,
extensions, and TimescaleDB hypertable. Subsequent migrations should be
produced by `alembic revision --autogenerate -m "..."`; the post-processing
hook in `migrations/env.py` injects further `create_hypertable(...)` calls
where models opt in via `info["timescale"]`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # for gen_random_uuid()

    # Schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS app;")
    op.execute("CREATE SCHEMA IF NOT EXISTS market;")

    # Enums (created in `app` schema; Bar references bar_granularity from market.bars)
    asset_class = postgresql.ENUM(
        "stock",
        "etf",
        "index",
        "crypto",
        "fx",
        "commodity",
        name="asset_class",
        schema="app",
    )
    asset_class.create(op.get_bind(), checkfirst=True)

    bar_granularity = postgresql.ENUM(
        "5m",
        "15m",
        "1h",
        "1d",
        name="bar_granularity",
        schema="app",
    )
    bar_granularity.create(op.get_bind(), checkfirst=True)

    # ---- users ----
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("authentik_sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("locale", sa.String(8), nullable=False, server_default="de"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("authentik_sub", name="uq_users_authentik_sub"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        schema="app",
    )
    op.create_index("ix_users_authentik_sub", "users", ["authentik_sub"], schema="app")
    op.create_index("ix_users_email", "users", ["email"], schema="app")

    # ---- assets ----
    op.create_table(
        "assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "asset_class",
            postgresql.ENUM(name="asset_class", schema="app", create_type=False),
            nullable=False,
        ),
        sa.Column("exchange", sa.String(32), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_symbol", sa.String(64), nullable=True),
        sa.Column("calendar", sa.String(16), nullable=False, server_default="XNYS"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "symbol",
            "asset_class",
            "source",
            name="uq_assets_symbol_class_source",
        ),
        schema="app",
    )
    op.create_index("ix_assets_symbol", "assets", ["symbol"], schema="app")
    op.create_index("ix_assets_asset_class", "assets", ["asset_class"], schema="app")

    # ---- bars (hypertable) ----
    op.create_table(
        "bars",
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.assets.id",
                ondelete="CASCADE",
                name="fk_bars_asset_id_assets",
            ),
            nullable=False,
        ),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "granularity",
            postgresql.ENUM(name="bar_granularity", schema="app", create_type=False),
            nullable=False,
        ),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(28, 8), nullable=True),
        sa.Column("adj_close", sa.Numeric(20, 8), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Composite PK (asset_id, time, granularity) is also the
        # idempotency key for ingest UPSERTs.
        sa.PrimaryKeyConstraint(
            "asset_id",
            "time",
            "granularity",
            name="pk_bars",
        ),
        schema="market",
    )
    op.create_index(
        "ix_bars_asset_time",
        "bars",
        ["asset_id", "time"],
        schema="market",
    )

    # Convert to hypertable. The 7-day chunk interval is a reasonable starting
    # point for 5-minute bars: roughly 2000 rows/day per asset → ~14k per
    # chunk per asset.
    op.execute(
        "SELECT create_hypertable("
        "'market.bars', 'time', "
        "chunk_time_interval => INTERVAL '7 days', "
        "if_not_exists => TRUE);"
    )

    # ---- watchlists ----
    op.create_table(
        "watchlists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.users.id",
                ondelete="CASCADE",
                name="fk_watchlists_user_id_users",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
        schema="app",
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"], schema="app")

    # ---- watchlist_assets ----
    op.create_table(
        "watchlist_assets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "watchlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.watchlists.id",
                ondelete="CASCADE",
                name="fk_watchlist_assets_watchlist_id_watchlists",
            ),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.assets.id",
                ondelete="CASCADE",
                name="fk_watchlist_assets_asset_id_assets",
            ),
            nullable=False,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "watchlist_id",
            "asset_id",
            name="uq_watchlist_assets_watchlist_asset",
        ),
        schema="app",
    )
    op.create_index(
        "ix_watchlist_assets_watchlist_id",
        "watchlist_assets",
        ["watchlist_id"],
        schema="app",
    )
    op.create_index(
        "ix_watchlist_assets_asset_id",
        "watchlist_assets",
        ["asset_id"],
        schema="app",
    )


def downgrade() -> None:
    # bars hypertable is torn down with its underlying table.
    op.drop_index("ix_watchlist_assets_asset_id", table_name="watchlist_assets", schema="app")
    op.drop_index("ix_watchlist_assets_watchlist_id", table_name="watchlist_assets", schema="app")
    op.drop_table("watchlist_assets", schema="app")

    op.drop_index("ix_watchlists_user_id", table_name="watchlists", schema="app")
    op.drop_table("watchlists", schema="app")

    op.drop_index("ix_bars_asset_time", table_name="bars", schema="market")
    op.drop_table("bars", schema="market")

    op.drop_index("ix_assets_asset_class", table_name="assets", schema="app")
    op.drop_index("ix_assets_symbol", table_name="assets", schema="app")
    op.drop_table("assets", schema="app")

    op.drop_index("ix_users_email", table_name="users", schema="app")
    op.drop_index("ix_users_authentik_sub", table_name="users", schema="app")
    op.drop_table("users", schema="app")

    postgresql.ENUM(name="bar_granularity", schema="app").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="asset_class", schema="app").drop(op.get_bind(), checkfirst=True)
