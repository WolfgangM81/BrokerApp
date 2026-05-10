"""Naive baseline: forward log-return = 0 (i.e. price stays put).

Useful as a sanity floor — any model that doesn't beat this on out-of-
sample backtests has no business being in production.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from brokerapp_ml.models.base import Forecaster, ForecastResult


class NaiveForecaster(Forecaster):
    name = "naive"

    def fit(self, features: pl.DataFrame, horizons: Sequence[int]) -> None:
        # Stateless.
        return

    def predict(self, features: pl.DataFrame, horizons: Sequence[int]) -> ForecastResult:
        return ForecastResult(
            horizons=tuple(horizons),
            point=tuple(0.0 for _ in horizons),
        )
