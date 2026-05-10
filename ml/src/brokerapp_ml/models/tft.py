"""Temporal Fusion Transformer + N-HiTS via Darts.

Both are wrapped behind the same `Forecaster` contract so callers don't
care which architecture they're using. Darts is an optional dependency:
the worker image installs it; tests stub it out.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import polars as pl

from brokerapp_ml.models.base import Forecaster, ForecastResult

ModelKind = Literal["tft", "nhits"]

MIN_OBSERVATIONS = 60


class DartsForecaster(Forecaster):
    """Wraps Darts' TFTModel / NHiTSModel.

    Args mirror the most-tuned hyperparameters; the rest stay at Darts
    defaults to keep the surface small. Sized small on purpose for the
    CPU-only homelab cluster (ADR-0005).
    """

    name: str = "darts"

    def __init__(
        self,
        kind: ModelKind = "tft",
        *,
        input_chunk_length: int = 64,
        output_chunk_length: int = 20,
        hidden_size: int = 16,
        n_epochs: int = 30,
        random_state: int = 42,
    ) -> None:
        self.kind = kind
        self.input_chunk_length = input_chunk_length
        self.output_chunk_length = output_chunk_length
        self.hidden_size = hidden_size
        self.n_epochs = n_epochs
        self.random_state = random_state
        self._model: object | None = None
        self._series: object | None = None
        self.name = kind

    def fit(self, features: pl.DataFrame, horizons: Sequence[int]) -> None:
        from darts import TimeSeries  # noqa: PLC0415  optional dep
        from darts.models import NHiTSModel, TFTModel  # noqa: PLC0415

        close = features["close"].drop_nulls().to_numpy()
        if close.size < MIN_OBSERVATIONS:
            self._model = None
            return
        log_returns = np.diff(np.log(close))
        series = TimeSeries.from_values(log_returns)
        common = {
            "input_chunk_length": self.input_chunk_length,
            "output_chunk_length": max(self.output_chunk_length, *horizons),
            "n_epochs": self.n_epochs,
            "random_state": self.random_state,
        }
        if self.kind == "tft":
            model = TFTModel(hidden_size=self.hidden_size, **common)
        else:
            model = NHiTSModel(num_blocks=2, num_layers=2, **common)
        model.fit(series, verbose=False)
        self._model = model
        self._series = series

    def predict(self, features: pl.DataFrame, horizons: Sequence[int]) -> ForecastResult:
        if self._model is None or self._series is None:
            return ForecastResult(horizons=tuple(horizons), point=tuple(0.0 for _ in horizons))
        max_h = max(horizons)
        forecast = self._model.predict(n=max_h, series=self._series)  # type: ignore[attr-defined]
        values = np.asarray(forecast.values()).flatten()
        cumulative = np.cumsum(values)
        return ForecastResult(
            horizons=tuple(horizons),
            point=tuple(float(cumulative[h - 1]) for h in horizons),
        )


__all__ = ["DartsForecaster", "ModelKind"]
