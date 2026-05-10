"""Stop-loss / take-profit recommendations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StopRecommendation:
    stop_loss: float
    take_profit: float


def fixed_pct_stop(
    entry_price: float,
    *,
    stop_pct: float = 0.05,
    take_profit_pct: float = 0.1,
    side: str = "long",
) -> StopRecommendation:
    """Symmetric percentage stop and take-profit relative to entry."""
    if entry_price <= 0:
        raise ValueError("entry_price must be positive.")
    if side not in {"long", "short"}:
        raise ValueError("side must be 'long' or 'short'.")
    if side == "long":
        return StopRecommendation(
            stop_loss=entry_price * (1.0 - stop_pct),
            take_profit=entry_price * (1.0 + take_profit_pct),
        )
    return StopRecommendation(
        stop_loss=entry_price * (1.0 + stop_pct),
        take_profit=entry_price * (1.0 - take_profit_pct),
    )


def atr_stop(
    entry_price: float,
    atr: float,
    *,
    atr_multiple: float = 2.0,
    rr: float = 2.0,
    side: str = "long",
) -> StopRecommendation:
    """ATR-based stop with a fixed reward-to-risk multiple.

    Args:
        entry_price: trade entry price.
        atr: current Average True Range value.
        atr_multiple: stop distance in ATRs (typically 1.5 to 3).
        rr: reward-to-risk ratio for the take-profit (typically 1.5 to 3).
    """
    if entry_price <= 0 or atr <= 0:
        raise ValueError("entry_price and atr must be positive.")
    distance = atr_multiple * atr
    if side == "long":
        return StopRecommendation(
            stop_loss=entry_price - distance,
            take_profit=entry_price + rr * distance,
        )
    return StopRecommendation(
        stop_loss=entry_price + distance,
        take_profit=entry_price - rr * distance,
    )


__all__ = ["StopRecommendation", "atr_stop", "fixed_pct_stop"]
