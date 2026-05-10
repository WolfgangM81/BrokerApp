"""Ensemble averages member predictions correctly."""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl
import pytest
from brokerapp_ml.models.base import Forecaster, ForecastResult
from brokerapp_ml.models.ensemble import EnsembleForecaster


class FixedForecaster(Forecaster):
    def __init__(self, value: float) -> None:
        self.name = "fixed"
        self.value = value

    def fit(self, features: pl.DataFrame, horizons: Sequence[int]) -> None:
        return

    def predict(self, features: pl.DataFrame, horizons: Sequence[int]) -> ForecastResult:
        return ForecastResult(horizons=tuple(horizons), point=tuple(self.value for _ in horizons))


def test_equal_weights_average() -> None:
    ens = EnsembleForecaster([FixedForecaster(1.0), FixedForecaster(3.0)])
    res = ens.predict(pl.DataFrame(), [1, 5])
    assert res.point == (2.0, 2.0)


def test_custom_weights_normalize() -> None:
    ens = EnsembleForecaster(
        [FixedForecaster(1.0), FixedForecaster(3.0)],
        weights=[3.0, 1.0],
    )
    # weighted = (3*1 + 1*3) / 4 = 1.5
    assert ens.predict(pl.DataFrame(), [1]).point == (1.5,)


def test_rejects_empty_members() -> None:
    with pytest.raises(ValueError):
        EnsembleForecaster([])


def test_rejects_zero_weight_sum() -> None:
    with pytest.raises(ValueError):
        EnsembleForecaster([FixedForecaster(1.0)], weights=[0.0])
