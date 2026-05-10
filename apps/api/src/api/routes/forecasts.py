"""Forecast and backtest read endpoints (Phase 3)."""

from __future__ import annotations

import os
import uuid
from typing import Annotated

import structlog
from brokerapp_db import Backtest, Forecast, ForecastHorizon, User
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, require_admin
from api.config import Settings, get_settings
from api.db import get_session
from api.errors import not_found
from api.schemas import BacktestOut, ForecastOut, ForecastRunResponse

router = APIRouter(prefix="/v1", tags=["forecasts"])
log = structlog.get_logger("api.forecasts")


@router.get("/assets/{asset_id}/forecasts", response_model=list[ForecastOut])
async def list_forecasts(
    asset_id: uuid.UUID,
    _user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    horizon: ForecastHorizon | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
) -> list[ForecastOut]:
    stmt = (
        select(Forecast)
        .where(Forecast.asset_id == asset_id)
        .order_by(Forecast.as_of.desc(), Forecast.horizon)
        .limit(limit)
    )
    if horizon is not None:
        stmt = stmt.where(Forecast.horizon == horizon)
    rows = (await session.execute(stmt)).scalars().all()
    return [ForecastOut.model_validate(r) for r in rows]


@router.get("/assets/{asset_id}/backtests", response_model=list[BacktestOut])
async def list_backtests(
    asset_id: uuid.UUID,
    _user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(20, ge=1, le=100),
) -> list[BacktestOut]:
    stmt = (
        select(Backtest)
        .where(Backtest.asset_id == asset_id)
        .order_by(Backtest.test_end.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [BacktestOut.model_validate(r) for r in rows]


@router.post(
    "/assets/{asset_id}/forecasts/run",
    response_model=ForecastRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
async def run_forecast(
    asset_id: uuid.UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    model: str = Query("lightgbm"),
) -> ForecastRunResponse:
    # Confirm the asset exists for nicer 404 vs accepted-then-fail UX.
    from brokerapp_db import Asset  # noqa: PLC0415  local to keep route imports tight

    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise not_found("asset.not_found", f"No asset with id {asset_id}.")
    _dispatch_forecast(asset_id, model, settings)
    return ForecastRunResponse(asset_id=asset_id, dispatched=True, model=model)


def _dispatch_forecast(asset_id: uuid.UUID, model: str, settings: Settings) -> None:
    if os.environ.get("BROKERAPP_DISABLE_CELERY_DISPATCH") == "1":
        log.info("forecast_dispatch_skipped", asset_id=str(asset_id))
        return
    try:
        from celery import Celery  # noqa: PLC0415  lazy

        app = Celery("brokerapp.dispatch", broker=str(settings.redis_url))
        app.send_task(
            "forecast.run_asset",
            args=[str(asset_id), model],
            queue="forecast",
        )
        log.info("forecast_dispatched", asset_id=str(asset_id), model=model)
    except Exception:
        log.exception("forecast_dispatch_failed", asset_id=str(asset_id))
