"""Average-of-models ensemble.

A more interesting Phase-5+ stacking ensemble would learn meta-weights
on out-of-fold predictions; for now we use a simple weighted average,
which already de-correlates noise across the baselines.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from brokerapp_ml.models.base import Forecaster, ForecastResult


class EnsembleForecaster(Forecaster):
    name = "ensemble"

    def __init__(
        self,
        members: Sequence[Forecaster],
        weights: Sequence[float] | None = None,
    ) -> None:
        if not members:
            raise ValueError("EnsembleForecaster requires at least one member.")
        self.members = list(members)
        if weights is None:
            self.weights = [1.0 / len(members)] * len(members)
        else:
            if len(weights) != len(members):
                raise ValueError("weights and members must have equal length.")
            total = sum(weights)
            if total == 0:
                raise ValueError("weights must not sum to zero.")
            self.weights = [w / total for w in weights]

    def fit(self, features: pl.DataFrame, horizons: Sequence[int]) -> None:
        for m in self.members:
            m.fit(features, horizons)

    def predict(self, features: pl.DataFrame, horizons: Sequence[int]) -> ForecastResult:
        per_horizon: list[float] = [0.0] * len(horizons)
        for m, w in zip(self.members, self.weights, strict=False):
            r = m.predict(features, horizons)
            for i, p in enumerate(r.point):
                per_horizon[i] += w * p
        return ForecastResult(horizons=tuple(horizons), point=tuple(per_horizon))


__all__ = ["EnsembleForecaster"]
