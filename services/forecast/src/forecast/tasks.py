"""Celery tasks for forecast training, inference, and walk-forward backtests."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from brokerapp_db import (
    Asset,
    Backtest,
    BarGranularity,
    ForecastHorizon,
    WatchlistAsset,
    session_scope,
)
from brokerapp_ml.backtests.engine import walk_forward_backtest
from brokerapp_ml.features.indicators import build_features
from brokerapp_ml.models.lightgbm_model import LightGBMForecaster
from brokerapp_ml.models.naive import NaiveForecaster
from sqlalchemy import select

from forecast.celery_app import celery_app
from forecast.db import get_session_factory
from forecast.repository import load_bars, upsert_forecast, upsert_model

log = structlog.get_logger("forecast.tasks")

MIN_BARS_FOR_FIT = 100
MIN_BARS_FOR_BACKTEST = 400

_HORIZON_DAYS: dict[ForecastHorizon, int] = {
    ForecastHorizon.h1: 1,
    ForecastHorizon.d1: 1,
    ForecastHorizon.d5: 5,
    ForecastHorizon.d20: 20,
}


def _instantiate(model_name: str):
    if model_name == "naive":
        return NaiveForecaster()
    if model_name == "lightgbm":
        return LightGBMForecaster()
    raise ValueError(f"Unknown model {model_name!r}")


@celery_app.task(name="forecast.run_asset", bind=True, max_retries=2)
def run_asset(self, asset_id: str, model_name: str = "lightgbm") -> dict[str, int]:
    """Train on the asset's full history and persist multi-horizon forecasts."""
    factory = get_session_factory()
    written = 0
    with session_scope(factory) as session:
        asset = session.get(Asset, uuid.UUID(asset_id))
        if asset is None:
            log.warning("forecast_asset_missing", asset_id=asset_id)
            return {"written": 0}
        bars = load_bars(session, asset.id, BarGranularity.d1)
        if bars.height < MIN_BARS_FOR_FIT:
            log.info("forecast_skip_too_few_bars", asset_id=asset_id, bars=bars.height)
            return {"written": 0}
        feats = build_features(bars, horizons=tuple(_HORIZON_DAYS.values()))
        forecaster = _instantiate(model_name)
        forecaster.fit(feats, list(_HORIZON_DAYS.values()))
        result = forecaster.predict(feats, list(_HORIZON_DAYS.values()))
        as_of: datetime = bars["time"].to_list()[-1]
        last_close = float(bars["close"].to_list()[-1])

        model = upsert_model(
            session,
            name=model_name,
            version=as_of.isoformat(),
        )
        for horizon, log_ret in zip(_HORIZON_DAYS, result.point, strict=False):
            target_time = as_of + timedelta(days=_HORIZON_DAYS[horizon])
            predicted_price = last_close * math.exp(log_ret)
            upsert_forecast(
                session,
                asset_id=asset.id,
                model_id=model.id,
                as_of=as_of,
                horizon=horizon,
                target_time=target_time,
                value=predicted_price,
                quantiles=None,
            )
            written += 1
    log.info("forecast_done", asset_id=asset_id, model=model_name, written=written)
    return {"written": written}


@celery_app.task(name="forecast.backtest_asset", bind=True, max_retries=1)
def backtest_asset(
    self,
    asset_id: str,
    model_name: str = "lightgbm",
    horizon_days: int = 5,
) -> dict[str, float]:
    factory = get_session_factory()
    with session_scope(factory) as session:
        asset = session.get(Asset, uuid.UUID(asset_id))
        if asset is None:
            return {"n": 0}
        bars = load_bars(session, asset.id, BarGranularity.d1)
        if bars.height < MIN_BARS_FOR_BACKTEST:
            return {"n": 0, "skipped": 1}
        forecaster = _instantiate(model_name)
        result = walk_forward_backtest(bars, forecaster, horizon=horizon_days)
        model = upsert_model(
            session,
            name=model_name,
            version=f"backtest-{result.test_end.isoformat()}",
            metrics=result.metrics,
        )
        h_enum = next(
            (h for h, d in _HORIZON_DAYS.items() if d == horizon_days),
            ForecastHorizon.d5,
        )
        session.add(
            Backtest(
                asset_id=asset.id,
                model_id=model.id,
                horizon=h_enum,
                train_start=result.train_start,
                train_end=result.train_end,
                test_start=result.test_start,
                test_end=result.test_end,
                metrics=result.metrics,
                config={"model": model_name, "horizon_days": str(horizon_days)},
            ),
        )
    return result.metrics


@celery_app.task(name="forecast.run_universe")
def run_universe(model_name: str = "lightgbm") -> dict[str, int]:
    """Fan-out: forecast every watched asset."""
    factory = get_session_factory()
    with session_scope(factory) as session:
        ids = [
            row[0]
            for row in session.execute(
                select(Asset.id)
                .join(WatchlistAsset, WatchlistAsset.asset_id == Asset.id)
                .where(Asset.enabled.is_(True))
                .distinct(),
            ).all()
        ]
    log.info("forecast_universe_dispatch", n=len(ids))
    for asset_id in ids:
        run_asset.apply_async(args=[str(asset_id), model_name], queue="forecast")
    return {"dispatched": len(ids)}


# Suppress linter for unused current-time helper
_ = datetime.now(UTC)
