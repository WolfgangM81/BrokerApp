"""Declarative SQLAlchemy base + naming conventions.

A consistent naming convention is essential for Alembic autogenerate to
produce stable, reviewable diffs. See:
https://alembic.sqlalchemy.org/en/latest/naming.html
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_label)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_label)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION, schema="app")


class Base(DeclarativeBase):
    """Project-wide declarative base.

    All metadata-attached tables go into the `app` schema by default; the
    `market` schema is reserved for the hypertable in `Bar.__table_args__`.
    """

    metadata = metadata

    type_annotation_map: dict[type, DateTime] = {datetime: DateTime(timezone=True)}  # noqa: RUF012  shared SQLAlchemy mapping


def utcnow() -> datetime:
    """UTC-aware now() used as default for created_at/updated_at."""
    return datetime.now(UTC)
