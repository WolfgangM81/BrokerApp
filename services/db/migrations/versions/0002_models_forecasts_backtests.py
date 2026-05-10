"""models, forecasts, backtests (Phase 3)

Revision ID: 0002_models_forecasts_backtests
Revises: 0001_initial_schema
Create Date: 2026-05-10 19:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_models_forecasts_backtests"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    horizon = postgresql.ENUM(
        "1h",
        "1d",
        "5d",
        "20d",
        name="forecast_horizon",
        schema="app",
    )
    horizon.create(op.get_bind(), checkfirst=True)
    status = postgresql.ENUM(
        "staging",
        "production",
        "archived",
        name="model_status",
        schema="app",
    )
    status.create(op.get_bind(), checkfirst=True)

    # ---- models ----
    op.create_table(
        "models",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column(
            "asset_class",
            postgresql.ENUM(name="asset_class", schema="app", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="model_status", schema="app", create_type=False),
            nullable=False,
            server_default="staging",
        ),
        sa.Column("mlflow_uri", sa.String(255), nullable=True),
        sa.Column("metrics", postgresql.JSONB, nullable=True),
        sa.Column("feature_schema", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("name", "version", name="uq_models_name_version"),
        schema="app",
    )

    # ---- forecasts ----
    op.create_table(
        "forecasts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.assets.id",
                ondelete="CASCADE",
                name="fk_forecasts_asset_id_assets",
            ),
            nullable=False,
        ),
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.models.id",
                ondelete="CASCADE",
                name="fk_forecasts_model_id_models",
            ),
            nullable=False,
        ),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "horizon",
            postgresql.ENUM(name="forecast_horizon", schema="app", create_type=False),
            nullable=False,
        ),
        sa.Column("target_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantiles", postgresql.JSONB, nullable=True),
        sa.Column("explain", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "asset_id",
            "model_id",
            "as_of",
            "horizon",
            name="uq_forecasts_asset_model_asof_horizon",
        ),
        schema="app",
    )
    op.create_index(
        "ix_forecasts_asset_asof",
        "forecasts",
        ["asset_id", "as_of"],
        schema="app",
    )
    op.create_index("ix_forecasts_asset_id", "forecasts", ["asset_id"], schema="app")
    op.create_index("ix_forecasts_model_id", "forecasts", ["model_id"], schema="app")

    # ---- backtests ----
    op.create_table(
        "backtests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.assets.id",
                ondelete="CASCADE",
                name="fk_backtests_asset_id_assets",
            ),
            nullable=False,
        ),
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "app.models.id",
                ondelete="CASCADE",
                name="fk_backtests_model_id_models",
            ),
            nullable=False,
        ),
        sa.Column(
            "horizon",
            postgresql.ENUM(name="forecast_horizon", schema="app", create_type=False),
            nullable=False,
        ),
        sa.Column("train_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("train_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", postgresql.JSONB, nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="app",
    )
    op.create_index("ix_backtests_asset_id", "backtests", ["asset_id"], schema="app")
    op.create_index("ix_backtests_model_id", "backtests", ["model_id"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_backtests_model_id", table_name="backtests", schema="app")
    op.drop_index("ix_backtests_asset_id", table_name="backtests", schema="app")
    op.drop_table("backtests", schema="app")
    op.drop_index("ix_forecasts_model_id", table_name="forecasts", schema="app")
    op.drop_index("ix_forecasts_asset_id", table_name="forecasts", schema="app")
    op.drop_index("ix_forecasts_asset_asof", table_name="forecasts", schema="app")
    op.drop_table("forecasts", schema="app")
    op.drop_table("models", schema="app")
    postgresql.ENUM(name="model_status", schema="app").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="forecast_horizon", schema="app").drop(op.get_bind(), checkfirst=True)
