"""Risk + position-sizing endpoints (Phase 6).

Stateless calculators — sizing is deterministic given the inputs, so
authenticated users can ask "given a forecast and my equity, what would
the recommendation be?". Persistent paper-portfolio P&L lives in
`paper_portfolios` + `trades` and is rolled up here.
"""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Literal

from brokerapp_db import PaperPortfolio, Trade, TradeSide, User
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user
from api.db import get_session
from api.errors import not_found

router = APIRouter(prefix="/v1", tags=["risk"])


class KellyRequest(BaseModel):
    win_prob: float = Field(ge=0, le=1)
    win_loss_ratio: float = Field(gt=0)
    cap: float = Field(default=0.25, gt=0, le=1)
    safety: float = Field(default=0.5, gt=0, le=1)


class FixedFractionalRequest(BaseModel):
    risk_per_trade: float = Field(gt=0, le=1)
    stop_distance_pct: float = Field(gt=0, le=1)


class VolTargetRequest(BaseModel):
    forecast_vol_daily: float = Field(gt=0)
    target_vol_annual: float = Field(default=0.15, gt=0, le=1)


class SizingResponse(BaseModel):
    fraction: float


class StopRequest(BaseModel):
    entry_price: float = Field(gt=0)
    atr: float | None = Field(default=None, gt=0)
    stop_pct: float = Field(default=0.05, gt=0, lt=1)
    take_profit_pct: float = Field(default=0.10, gt=0, lt=1)
    atr_multiple: float = Field(default=2.0, gt=0)
    rr: float = Field(default=2.0, gt=0)
    side: Literal["long", "short"] = "long"


class StopResponse(BaseModel):
    stop_loss: float
    take_profit: float


class PaperPortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_currency: str
    starting_cash: float
    strategy: str | None


class PaperPortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    base_currency: str = Field(default="EUR", min_length=3, max_length=3)
    starting_cash: float = Field(gt=0)
    strategy: str | None = Field(default=None, max_length=64)


class PaperPortfolioSummary(BaseModel):
    id: uuid.UUID
    name: str
    starting_cash: float
    cash: float
    realized_pnl: float
    n_trades: int


@router.post("/risk/sizing/kelly", response_model=SizingResponse)
async def kelly(
    payload: KellyRequest,
    _user: Annotated[User, Depends(current_user)],
) -> SizingResponse:
    from brokerapp_ml.risk.sizing import kelly_fraction  # noqa: PLC0415  optional dep

    return SizingResponse(
        fraction=kelly_fraction(
            payload.win_prob,
            payload.win_loss_ratio,
            cap=payload.cap,
            safety=payload.safety,
        ),
    )


@router.post("/risk/sizing/fixed-fractional", response_model=SizingResponse)
async def fixed_fractional_endpoint(
    payload: FixedFractionalRequest,
    _user: Annotated[User, Depends(current_user)],
) -> SizingResponse:
    from brokerapp_ml.risk.sizing import fixed_fractional  # noqa: PLC0415

    return SizingResponse(
        fraction=fixed_fractional(payload.risk_per_trade, payload.stop_distance_pct)
    )


@router.post("/risk/sizing/vol-target", response_model=SizingResponse)
async def vol_target_endpoint(
    payload: VolTargetRequest,
    _user: Annotated[User, Depends(current_user)],
) -> SizingResponse:
    from brokerapp_ml.risk.sizing import vol_target  # noqa: PLC0415

    return SizingResponse(
        fraction=vol_target(payload.forecast_vol_daily, payload.target_vol_annual),
    )


@router.post("/risk/stops", response_model=StopResponse)
async def stops(
    payload: StopRequest,
    _user: Annotated[User, Depends(current_user)],
) -> StopResponse:
    from brokerapp_ml.risk.stops import atr_stop, fixed_pct_stop  # noqa: PLC0415

    if payload.atr is not None:
        rec = atr_stop(
            payload.entry_price,
            payload.atr,
            atr_multiple=payload.atr_multiple,
            rr=payload.rr,
            side=payload.side,
        )
    else:
        rec = fixed_pct_stop(
            payload.entry_price,
            stop_pct=payload.stop_pct,
            take_profit_pct=payload.take_profit_pct,
            side=payload.side,
        )
    return StopResponse(stop_loss=rec.stop_loss, take_profit=rec.take_profit)


# --- paper portfolios -------------------------------------------------------


@router.get("/paper-portfolios", response_model=list[PaperPortfolioOut])
async def list_portfolios(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PaperPortfolioOut]:
    rows = (
        (
            await session.execute(
                select(PaperPortfolio)
                .where(PaperPortfolio.user_id == user.id)
                .order_by(PaperPortfolio.name),
            )
        )
        .scalars()
        .all()
    )
    return [
        PaperPortfolioOut(
            id=r.id,
            name=r.name,
            base_currency=r.base_currency,
            starting_cash=float(r.starting_cash),
            strategy=r.strategy,
        )
        for r in rows
    ]


@router.post(
    "/paper-portfolios",
    response_model=PaperPortfolioOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_portfolio(
    payload: PaperPortfolioCreate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaperPortfolioOut:
    portfolio = PaperPortfolio(
        user_id=user.id,
        name=payload.name,
        base_currency=payload.base_currency,
        starting_cash=payload.starting_cash,
        strategy=payload.strategy,
    )
    session.add(portfolio)
    await session.flush()
    await session.commit()
    return PaperPortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        base_currency=portfolio.base_currency,
        starting_cash=float(portfolio.starting_cash),
        strategy=portfolio.strategy,
    )


@router.get("/paper-portfolios/{portfolio_id}/summary", response_model=PaperPortfolioSummary)
async def portfolio_summary(
    portfolio_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaperPortfolioSummary:
    portfolio = await session.get(PaperPortfolio, portfolio_id)
    if portfolio is None or portfolio.user_id != user.id:
        raise not_found("paper_portfolio.not_found", f"No paper portfolio with id {portfolio_id}.")

    trades = (
        (
            await session.execute(
                select(Trade)
                .where(Trade.user_id == user.id, Trade.paper.is_(True))
                .order_by(Trade.traded_at),
            )
        )
        .scalars()
        .all()
    )
    cash = float(portfolio.starting_cash)
    realized = 0.0
    for trade in trades:
        flow = float(trade.quantity) * float(trade.price)
        if trade.side is TradeSide.buy:
            cash -= flow
        else:
            cash += flow
            realized += flow  # naive realized-PnL proxy until we add lot tracking
    if math.isnan(cash):
        cash = 0.0
    return PaperPortfolioSummary(
        id=portfolio.id,
        name=portfolio.name,
        starting_cash=float(portfolio.starting_cash),
        cash=cash,
        realized_pnl=realized,
        n_trades=len(trades),
    )
