"""Bars endpoint — read OHLCV for an asset at a granularity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from brokerapp_db import Asset, Bar, BarGranularity, User
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user
from api.db import get_session
from api.errors import bad_request, not_found
from api.schemas import BarOut, BarsResponse

router = APIRouter(prefix="/v1/assets", tags=["bars"])

MAX_BARS_PER_REQUEST = 5000


@router.get("/{asset_id}/bars", response_model=BarsResponse)
async def get_bars(
    asset_id: uuid.UUID,
    _user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    granularity: BarGranularity = Query(BarGranularity.d1),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=MAX_BARS_PER_REQUEST),
) -> BarsResponse:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise not_found("asset.not_found", f"No asset with id {asset_id}.")

    if from_ is not None and to is not None and from_ >= to:
        raise bad_request(
            "bars.invalid_range",
            "`from` must be strictly less than `to`.",
        )

    stmt = (
        select(Bar)
        .where(Bar.asset_id == asset_id, Bar.granularity == granularity)
        .order_by(Bar.time.asc())
        .limit(limit)
    )
    if from_ is not None:
        stmt = stmt.where(Bar.time >= from_)
    if to is not None:
        stmt = stmt.where(Bar.time < to)

    rows = (await session.execute(stmt)).scalars().all()
    return BarsResponse(
        asset_id=asset_id,
        granularity=granularity,
        bars=[BarOut.model_validate(r) for r in rows],
    )
