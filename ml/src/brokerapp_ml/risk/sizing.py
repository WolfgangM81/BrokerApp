"""Position-sizing rules.

Each function returns a fraction of capital `f` in `[0, 1]` (or `[-1, 0]`
for shorts) — the caller multiplies by the portfolio's available cash to
get the trade size.
"""

from __future__ import annotations

import math


def kelly_fraction(
    win_prob: float,
    win_loss_ratio: float,
    *,
    cap: float = 0.25,
    safety: float = 0.5,
) -> float:
    """Fractional Kelly with a hard cap and a half-Kelly safety multiplier.

    Args:
        win_prob: probability of a winning trade in `[0, 1]`.
        win_loss_ratio: average winner divided by average loser (positive).
        cap: hard upper bound on the returned fraction.
        safety: multiplier applied to the raw Kelly fraction (0.5 = half-Kelly).
    """
    if not 0.0 <= win_prob <= 1.0 or win_loss_ratio <= 0:
        return 0.0
    raw = win_prob - (1.0 - win_prob) / win_loss_ratio
    return max(0.0, min(cap, safety * raw))


def fixed_fractional(
    risk_per_trade: float,
    stop_distance_pct: float,
) -> float:
    """Fixed-fractional sizing: risk a constant `risk_per_trade` of equity per trade.

    `risk_per_trade` is a fraction of total equity (e.g. 0.01 = 1%).
    `stop_distance_pct` is the distance to the stop as a fraction of price
    (e.g. 0.05 = 5% below entry).
    """
    if stop_distance_pct <= 0 or risk_per_trade <= 0:
        return 0.0
    return min(1.0, risk_per_trade / stop_distance_pct)


def vol_target(
    forecast_vol_daily: float,
    target_vol_annual: float = 0.15,
    *,
    cap: float = 1.0,
) -> float:
    """Vol-targeting: scale exposure inversely to forecasted realised volatility.

    Args:
        forecast_vol_daily: forecasted standard deviation of daily returns.
        target_vol_annual: desired annualised portfolio volatility (e.g. 15%).
        cap: maximum exposure (1.0 = fully invested).
    """
    if forecast_vol_daily <= 0:
        return 0.0
    annualized = forecast_vol_daily * math.sqrt(252)
    return min(cap, target_vol_annual / annualized)


__all__ = ["fixed_fractional", "kelly_fraction", "vol_target"]
