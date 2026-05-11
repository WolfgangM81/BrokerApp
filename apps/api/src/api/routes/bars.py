"""Bars endpoint — read OHLCV for an asset at a granularity.

Behind the scenes:
- 5m and 1d are served from `market.bars` directly.
- 15m and 1h are served from the continuous-aggregate views created by
  Alembic migration 0004 (see `brokerapp_db.queries.fetch_bars`).

We also emit `Cache-Control: public, max-age=86400, immutable` whenever
the caller has bounded the range to "everything before yesterday" —
historical OHLCV doesn't change, so the browser / CDN can cache it
indefinitely (in practice: a day, after which we re-check in case of
provider corrections).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from brokerapp_db import Asset, BarGranularity, User, fetch_bars
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user
from api.db import get_session
from api.errors import bad_request, not_found
from api.schemas import BarOut, BarsResponse

router = APIRouter(prefix="/v1/assets", tags=["bars"])

MAX_BARS_PER_REQUEST = 5000

# Window we treat as "still live" — within this many hours of `now`, we
# don't emit aggressive caching headers because new bars may still land.
_LIVE_WINDOW = timedelta(hours=36)
_HISTORICAL_CACHE_HEADER = "public, max-age=86400, immutable"


def _historical_cache_header(to: datetime | None) -> str | None:
    """Return the Cache-Control header value when `to` is fully historical."""
    if to is None:
        return None
    cutoff = datetime.now(UTC) - _LIVE_WINDOW
    to_aware = to if to.tzinfo else to.replace(tzinfo=UTC)
    if to_aware < cutoff:
        return _HISTORICAL_CACHE_HEADER
    return None


@router.get("/{asset_id}/bars", response_model=BarsResponse)
async def get_bars(
    asset_id: uuid.UUID,
    response: Response,
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

    rows = await fetch_bars(
        session,
        asset_id=asset_id,
        granularity=granularity,
        start=from_,
        end=to,
        limit=limit,
    )

    cache_header = _historical_cache_header(to)
    if cache_header is not None:
        response.headers["Cache-Control"] = cache_header

    return BarsResponse(
        asset_id=asset_id,
        granularity=granularity,
        bars=[BarOut.model_validate(r) for r in rows],
    )
