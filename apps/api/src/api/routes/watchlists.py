"""Watchlist CRUD + member-add (triggers ingest backfill).

Adding an asset to *any* of the user's watchlists is the only way an
asset's history starts flowing into the DB in Phase 1 — see ADR notes
on the watchlist-driven bootstrap.
"""

from __future__ import annotations

import os
import uuid
from typing import Annotated

import structlog
from brokerapp_db import Asset, User, Watchlist, WatchlistAsset
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import current_user
from api.config import Settings, get_settings
from api.db import get_session
from api.errors import bad_request, conflict, not_found
from api.schemas import (
    WatchlistCreate,
    WatchlistDetail,
    WatchlistMemberAdd,
    WatchlistOut,
    WatchlistUpdate,
)

router = APIRouter(prefix="/v1/watchlists", tags=["watchlists"])

log = structlog.get_logger("api.watchlists")


@router.get("", response_model=list[WatchlistOut])
async def list_watchlists(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WatchlistOut]:
    stmt = select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.name)
    rows = (await session.execute(stmt)).scalars().all()
    return [WatchlistOut.model_validate(r) for r in rows]


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    payload: WatchlistCreate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WatchlistOut:
    watchlist = Watchlist(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
    )
    session.add(watchlist)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict(
            "watchlist.name_taken",
            f"A watchlist named {payload.name!r} already exists.",
        ) from exc
    await session.commit()
    return WatchlistOut.model_validate(watchlist)


@router.get("/{watchlist_id}", response_model=WatchlistDetail)
async def get_watchlist(
    watchlist_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WatchlistDetail:
    stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.members))
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == user.id)
    )
    watchlist = (await session.execute(stmt)).scalar_one_or_none()
    if watchlist is None:
        raise not_found("watchlist.not_found", f"No watchlist with id {watchlist_id}.")
    return WatchlistDetail.model_validate(watchlist)


@router.patch("/{watchlist_id}", response_model=WatchlistOut)
async def update_watchlist(
    watchlist_id: uuid.UUID,
    payload: WatchlistUpdate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WatchlistOut:
    watchlist = await session.get(Watchlist, watchlist_id)
    if watchlist is None or watchlist.user_id != user.id:
        raise not_found("watchlist.not_found", f"No watchlist with id {watchlist_id}.")
    if payload.name is not None:
        watchlist.name = payload.name
    if payload.description is not None:
        watchlist.description = payload.description
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict(
            "watchlist.name_taken",
            "Another watchlist with that name already exists.",
        ) from exc
    await session.commit()
    return WatchlistOut.model_validate(watchlist)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    watchlist = await session.get(Watchlist, watchlist_id)
    if watchlist is None or watchlist.user_id != user.id:
        raise not_found("watchlist.not_found", f"No watchlist with id {watchlist_id}.")
    await session.delete(watchlist)
    await session.commit()


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


def _trigger_backfill(asset_id: uuid.UUID, settings: Settings) -> None:
    """Dispatch the ingest backfill task.

    Imported lazily so the API container doesn't need the full Celery /
    broker config at import time during tests.
    """
    if os.environ.get("BROKERAPP_DISABLE_CELERY_DISPATCH") == "1":
        log.info("backfill_dispatch_skipped", asset_id=str(asset_id), reason="disabled")
        return
    try:
        from celery import Celery  # noqa: PLC0415  lazy import keeps test-time imports cheap

        broker = str(settings.redis_url)
        app = Celery("brokerapp.dispatch", broker=broker)
        app.send_task(
            "ingest.backfill_asset",
            args=[str(asset_id), settings.backfill_years],
            queue="ingest",
        )
        log.info("backfill_dispatched", asset_id=str(asset_id))
    except Exception:
        log.exception("backfill_dispatch_failed", asset_id=str(asset_id))


@router.post(
    "/{watchlist_id}/members",
    response_model=WatchlistDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    watchlist_id: uuid.UUID,
    payload: WatchlistMemberAdd,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WatchlistDetail:
    watchlist = await session.get(Watchlist, watchlist_id)
    if watchlist is None or watchlist.user_id != user.id:
        raise not_found("watchlist.not_found", f"No watchlist with id {watchlist_id}.")

    asset = await session.get(Asset, payload.asset_id)
    if asset is None:
        raise not_found("asset.not_found", f"No asset with id {payload.asset_id}.")
    if not asset.enabled:
        raise bad_request("asset.disabled", "Asset is disabled.")

    member = WatchlistAsset(watchlist_id=watchlist.id, asset_id=asset.id)
    session.add(member)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict(
            "watchlist.member_already_added",
            "Asset is already on this watchlist.",
        ) from exc
    await session.commit()

    _trigger_backfill(asset.id, settings)

    detail = await get_watchlist(watchlist_id, user, session)  # reuse loader
    return detail


@router.delete(
    "/{watchlist_id}/members/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    watchlist_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    watchlist = await session.get(Watchlist, watchlist_id)
    if watchlist is None or watchlist.user_id != user.id:
        raise not_found("watchlist.not_found", f"No watchlist with id {watchlist_id}.")
    stmt = select(WatchlistAsset).where(
        WatchlistAsset.watchlist_id == watchlist_id,
        WatchlistAsset.asset_id == asset_id,
    )
    member = (await session.execute(stmt)).scalar_one_or_none()
    if member is None:
        raise not_found(
            "watchlist.member_not_found",
            "Asset is not on this watchlist.",
        )
    await session.delete(member)
    await session.commit()
