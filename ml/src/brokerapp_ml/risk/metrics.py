"""Portfolio-level risk metrics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

ANNUALIZATION_DAYS = 252


@dataclass(frozen=True, slots=True)
class PortfolioMetrics:
    sharpe: float
    sortino: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    annualized_return: float
    annualized_vol: float


def _arr(returns: Iterable[float]) -> np.ndarray:
    return np.asarray(list(returns), dtype=float)


def sharpe_ratio(returns: Iterable[float], risk_free_daily: float = 0.0) -> float:
    r = _arr(returns)
    if r.size == 0 or r.std(ddof=0) == 0:
        return 0.0
    excess = r - risk_free_daily
    return float(np.sqrt(ANNUALIZATION_DAYS) * excess.mean() / r.std(ddof=0))


def sortino_ratio(returns: Iterable[float], risk_free_daily: float = 0.0) -> float:
    r = _arr(returns)
    if r.size == 0:
        return 0.0
    excess = r - risk_free_daily
    downside = r[r < risk_free_daily]
    denom = downside.std(ddof=0) if downside.size else 0.0
    if denom == 0:
        return 0.0
    return float(np.sqrt(ANNUALIZATION_DAYS) * excess.mean() / denom)


def max_drawdown(returns: Iterable[float]) -> float:
    """Return the most-negative peak-to-trough drawdown of a cumulative return path."""
    r = _arr(returns)
    if r.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    return float(drawdown.min())


def var(returns: Iterable[float], alpha: float = 0.05) -> float:
    """Historical Value-at-Risk at confidence `1 - alpha` (positive number)."""
    r = _arr(returns)
    if r.size == 0:
        return 0.0
    return float(-np.quantile(r, alpha))


def cvar(returns: Iterable[float], alpha: float = 0.05) -> float:
    """Conditional VaR (expected shortfall) at confidence `1 - alpha`."""
    r = _arr(returns)
    if r.size == 0:
        return 0.0
    threshold = np.quantile(r, alpha)
    tail = r[r <= threshold]
    if tail.size == 0:
        return 0.0
    return float(-tail.mean())


def portfolio_metrics(
    returns: Iterable[float],
    *,
    risk_free_daily: float = 0.0,
    alpha: float = 0.05,
) -> PortfolioMetrics:
    r = _arr(returns)
    if r.size == 0:
        zero = PortfolioMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return zero
    return PortfolioMetrics(
        sharpe=sharpe_ratio(r, risk_free_daily),
        sortino=sortino_ratio(r, risk_free_daily),
        max_drawdown=max_drawdown(r),
        var_95=var(r, alpha),
        cvar_95=cvar(r, alpha),
        annualized_return=float(np.prod(1.0 + r) ** (ANNUALIZATION_DAYS / r.size) - 1.0),
        annualized_vol=float(r.std(ddof=0) * np.sqrt(ANNUALIZATION_DAYS)),
    )


__all__ = [
    "ANNUALIZATION_DAYS",
    "PortfolioMetrics",
    "cvar",
    "max_drawdown",
    "portfolio_metrics",
    "sharpe_ratio",
    "sortino_ratio",
    "var",
]
