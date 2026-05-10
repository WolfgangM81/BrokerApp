"""Forecaster contract.

Every baseline implements `fit(features)` and `predict(features)` returning
log-return forecasts at the requested horizons. Models do not see the
target columns at predict time; the caller is responsible for stripping
them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True, slots=True)
class ForecastResult:
    """One row of forecasts for one (asset, as_of) tuple."""

    horizons: tuple[int, ...]
    point: tuple[float, ...]
    quantiles: dict[str, tuple[float, ...]] | None = None


class Forecaster(ABC):
    """Stateful, fittable forecaster of forward log-returns."""

    name: str

    @abstractmethod
    def fit(self, features: pl.DataFrame, horizons: Sequence[int]) -> None: ...

    @abstractmethod
    def predict(self, features: pl.DataFrame, horizons: Sequence[int]) -> ForecastResult: ...


__all__ = ["ForecastResult", "Forecaster"]
