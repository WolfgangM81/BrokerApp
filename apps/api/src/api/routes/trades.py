"""Trade-journal endpoints (Phase 4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from brokerapp_db import Asset, Trade, TradeSide, User
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user
from api.db import get_session
from api.errors import not_found

router = APIRouter(prefix="/v1/trades", tags=["trades"])


class TradeCreate(BaseModel):
    asset_id: uuid.UUID
    side: TradeSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    traded_at: datetime
    notes: str | None = Field(default=None, max_length=2048)
    paper: bool = True


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    side: TradeSide
    quantity: Decimal
    price: Decimal
    traded_at: datetime
    notes: str | None
    paper: bool


@router.get("", response_model=list[TradeOut])
async def list_trades(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    asset_id: uuid.UUID | None = Query(None),
    paper: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[TradeOut]:
    stmt = (
        select(Trade).where(Trade.user_id == user.id).order_by(Trade.traded_at.desc()).limit(limit)
    )
    if asset_id is not None:
        stmt = stmt.where(Trade.asset_id == asset_id)
    if paper is not None:
        stmt = stmt.where(Trade.paper.is_(paper))
    rows = (await session.execute(stmt)).scalars().all()
    return [TradeOut.model_validate(r) for r in rows]


@router.post("", response_model=TradeOut, status_code=status.HTTP_201_CREATED)
async def create_trade(
    payload: TradeCreate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TradeOut:
    asset = (
        await session.execute(select(Asset).where(and_(Asset.id == payload.asset_id)))
    ).scalar_one_or_none()
    if asset is None:
        raise not_found("asset.not_found", f"No asset with id {payload.asset_id}.")
    trade = Trade(
        user_id=user.id,
        asset_id=payload.asset_id,
        side=payload.side,
        quantity=payload.quantity,
        price=payload.price,
        traded_at=payload.traded_at,
        notes=payload.notes,
        paper=payload.paper,
    )
    session.add(trade)
    await session.flush()
    await session.commit()
    return TradeOut.model_validate(trade)


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    trade = await session.get(Trade, trade_id)
    if trade is None or trade.user_id != user.id:
        raise not_found("trade.not_found", f"No trade with id {trade_id}.")
    await session.delete(trade)
    await session.commit()
