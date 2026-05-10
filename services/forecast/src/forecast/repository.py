"""DB helpers for the forecast worker."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import polars as pl
from brokerapp_db import (
    Bar,
    BarGranularity,
    Forecast,
    ForecastHorizon,
    Model,
    ModelStatus,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session


def load_bars(
    session: Session,
    asset_id: uuid.UUID,
    granularity: BarGranularity,
    *,
    limit: int | None = None,
) -> pl.DataFrame:
    stmt = (
        select(Bar)
        .where(Bar.asset_id == asset_id, Bar.granularity == granularity)
        .order_by(Bar.time.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = session.execute(stmt).scalars().all()
    if not rows:
        return pl.DataFrame(
            schema={
                "time": pl.Datetime(time_zone="UTC"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
                "adj_close": pl.Float64,
            },
        )
    return pl.DataFrame(
        {
            "time": [r.time for r in rows],
            "open": [float(r.open) for r in rows],
            "high": [float(r.high) for r in rows],
            "low": [float(r.low) for r in rows],
            "close": [float(r.close) for r in rows],
            "volume": [float(r.volume) if r.volume is not None else None for r in rows],
            "adj_close": [float(r.adj_close) if r.adj_close is not None else None for r in rows],
        },
        schema_overrides={"time": pl.Datetime(time_zone="UTC")},
    )


def upsert_model(
    session: Session,
    *,
    name: str,
    version: str,
    mlflow_uri: str | None = None,
    metrics: dict[str, float] | None = None,
    feature_schema: dict[str, str] | None = None,
) -> Model:
    existing = session.execute(
        select(Model).where(Model.name == name, Model.version == version),
    ).scalar_one_or_none()
    if existing is not None:
        if mlflow_uri:
            existing.mlflow_uri = mlflow_uri
        if metrics is not None:
            existing.metrics = metrics
        return existing
    model = Model(
        name=name,
        version=version,
        mlflow_uri=mlflow_uri,
        metrics=metrics,
        feature_schema=feature_schema,
        status=ModelStatus.staging,
    )
    session.add(model)
    session.flush()
    return model


def upsert_forecast(
    session: Session,
    *,
    asset_id: uuid.UUID,
    model_id: uuid.UUID,
    as_of: datetime,
    horizon: ForecastHorizon,
    target_time: datetime,
    value: float,
    quantiles: dict[str, float] | None = None,
) -> None:
    stmt = pg_insert(Forecast).values(
        asset_id=asset_id,
        model_id=model_id,
        as_of=as_of,
        horizon=horizon,
        target_time=target_time,
        value=Decimal(str(value)),
        quantiles=quantiles,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            Forecast.asset_id,
            Forecast.model_id,
            Forecast.as_of,
            Forecast.horizon,
        ],
        set_={
            "value": stmt.excluded.value,
            "target_time": stmt.excluded.target_time,
            "quantiles": stmt.excluded.quantiles,
        },
    )
    session.execute(stmt)


__all__ = ["load_bars", "upsert_forecast", "upsert_model"]
