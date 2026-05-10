"""Asset endpoints (read + admin create / discovery)."""

from __future__ import annotations

import uuid
from typing import Annotated

from brokerapp_db import Asset, AssetClass, User
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, require_admin
from api.db import get_session
from api.errors import conflict, not_found
from api.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Page,
    decode_cursor,
    encode_cursor,
)
from api.schemas import AssetCreate, AssetOut

router = APIRouter(prefix="/v1/assets", tags=["assets"])


@router.get("", response_model=Page[AssetOut])
async def list_assets(
    _user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    asset_class: AssetClass | None = Query(None, description="Filter by class"),
    q: str | None = Query(None, max_length=64, description="Symbol/name search"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: str | None = Query(None, max_length=256),
) -> Page[AssetOut]:
    stmt = select(Asset).where(Asset.enabled.is_(True)).order_by(Asset.symbol)
    if asset_class is not None:
        stmt = stmt.where(Asset.asset_class == asset_class)
    if q:
        like = f"%{q.upper()}%"
        stmt = stmt.where(Asset.symbol.ilike(like) | Asset.name.ilike(like))
    if cursor:
        token = decode_cursor(cursor)
        if token and "after_symbol" in token:
            stmt = stmt.where(Asset.symbol > str(token["after_symbol"]))
    stmt = stmt.limit(limit + 1)

    rows = (await session.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor({"after_symbol": rows[-1].symbol}) if has_more and rows else None
    return Page[AssetOut](
        items=[AssetOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: uuid.UUID,
    _user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetOut:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise not_found("asset.not_found", f"No asset with id {asset_id}.")
    return AssetOut.model_validate(asset)


@router.post(
    "",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_asset(
    payload: AssetCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetOut:
    # Reject obvious duplicates eagerly; the unique constraint is the
    # ultimate authority.
    existing = await session.execute(
        select(Asset).where(
            and_(
                Asset.symbol == payload.symbol,
                Asset.asset_class == payload.asset_class,
                Asset.source == payload.source,
            ),
        ),
    )
    if existing.scalar_one_or_none() is not None:
        raise conflict(
            "asset.already_exists",
            f"{payload.source}:{payload.symbol} ({payload.asset_class.value}) already exists.",
        )

    asset = Asset(
        symbol=payload.symbol.upper(),
        name=payload.name,
        asset_class=payload.asset_class,
        exchange=payload.exchange,
        currency=payload.currency,
        source=payload.source,
        source_symbol=payload.source_symbol or payload.symbol,
        calendar=payload.calendar,
    )
    session.add(asset)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict(
            "asset.already_exists",
            "Asset violates a uniqueness constraint.",
        ) from exc
    await session.commit()
    return AssetOut.model_validate(asset)
