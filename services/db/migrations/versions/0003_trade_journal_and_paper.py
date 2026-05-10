"""trade journal + paper portfolios (Phase 4)

Revision ID: 0003_trade_journal_and_paper
Revises: 0002_models_forecasts_backtests
Create Date: 2026-05-10 19:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_trade_journal_and_paper"
down_revision: str | Sequence[str] | None = "0002_models_forecasts_backtests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    side = postgresql.ENUM("buy", "sell", name="trade_side", schema="app")
    side.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.users.id", ondelete="CASCADE", name="fk_trades_user_id_users"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app.assets.id", ondelete="CASCADE", name="fk_trades_asset_id_assets"),
            nullable=False,
        ),
        sa.Column(
            "side",
            postgresql.ENUM(name="trade_side", schema="app", create_type=False),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("traded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("paper", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="app",
    )
    op.create_index("ix_trades_user_id", "trades", ["user_id"], schema="app")
    op.create_index("ix_trades_asset_id", "trades", ["asset_id"], schema="app")

    op.create_table(
        "paper_portfolios",
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
                name="fk_paper_portfolios_user_id_users",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("starting_cash", sa.Numeric(20, 2), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_paper_portfolios_user_name"),
        schema="app",
    )
    op.create_index(
        "ix_paper_portfolios_user_id",
        "paper_portfolios",
        ["user_id"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index("ix_paper_portfolios_user_id", table_name="paper_portfolios", schema="app")
    op.drop_table("paper_portfolios", schema="app")
    op.drop_index("ix_trades_asset_id", table_name="trades", schema="app")
    op.drop_index("ix_trades_user_id", table_name="trades", schema="app")
    op.drop_table("trades", schema="app")
    postgresql.ENUM(name="trade_side", schema="app").drop(op.get_bind(), checkfirst=True)
