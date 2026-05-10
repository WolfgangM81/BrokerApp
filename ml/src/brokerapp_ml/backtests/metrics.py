"""Forecast-evaluation metrics. Pure NumPy / Polars; no plotting."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np


def regression_metrics(y_true: Iterable[float], y_pred: Iterable[float]) -> dict[str, float]:
    """MAE / RMSE / bias on log-returns."""
    yt = np.asarray(list(y_true), dtype=float)
    yp = np.asarray(list(y_pred), dtype=float)
    if yt.size == 0:
        return {"mae": float("nan"), "rmse": float("nan"), "bias": float("nan")}
    err = yp - yt
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(math.sqrt(float(np.mean(err**2)))),
        "bias": float(np.mean(err)),
    }


def directional_metrics(y_true: Iterable[float], y_pred: Iterable[float]) -> dict[str, float]:
    """Hit-rate (sign match), Sharpe of a sign-following strategy.

    Sharpe is computed on the *realized* log-returns when traded according
    to the predicted sign, annualized assuming `~252` daily observations.
    """
    yt = np.asarray(list(y_true), dtype=float)
    yp = np.asarray(list(y_pred), dtype=float)
    if yt.size == 0:
        return {"hit_rate": float("nan"), "sharpe": float("nan"), "max_drawdown": float("nan")}
    direction = np.sign(yp)
    pnl = direction * yt
    hit = float(np.mean(np.sign(yp) == np.sign(yt)))
    sharpe = float(np.sqrt(252) * pnl.mean() / pnl.std(ddof=0)) if pnl.std(ddof=0) > 0 else 0.0
    equity = np.cumsum(pnl)
    drawdown = equity - np.maximum.accumulate(equity)
    max_dd = float(drawdown.min()) if drawdown.size else 0.0
    return {"hit_rate": hit, "sharpe": sharpe, "max_drawdown": max_dd}


__all__ = ["directional_metrics", "regression_metrics"]
