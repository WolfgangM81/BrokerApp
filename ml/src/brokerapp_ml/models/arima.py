"""ARIMA baseline on log-returns."""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from brokerapp_ml.models.base import Forecaster, ForecastResult

MIN_OBSERVATIONS = 30


class ARIMAForecaster(Forecaster):
    name = "arima"

    def __init__(self, order: tuple[int, int, int] = (1, 0, 1)) -> None:
        self.order = order
        self._result = None

    def fit(self, features: pl.DataFrame, horizons: Sequence[int]) -> None:
        from statsmodels.tsa.arima.model import ARIMA  # noqa: PLC0415  optional dep

        series = features["log_return_1d"].drop_nulls().to_numpy()
        if len(series) < MIN_OBSERVATIONS:
            self._result = None
            return
        model = ARIMA(series, order=self.order, enforce_stationarity=False)
        self._result = model.fit(method_kwargs={"warn_convergence": False})

    def predict(self, features: pl.DataFrame, horizons: Sequence[int]) -> ForecastResult:
        max_h = max(horizons)
        if self._result is None:
            return ForecastResult(horizons=tuple(horizons), point=tuple(0.0 for _ in horizons))
        forecast = self._result.forecast(steps=max_h)
        # Cumulative log-return at each requested horizon (sum of predicted
        # 1-step log-returns).
        cum = 0.0
        cumulative: list[float] = []
        for i in range(max_h):
            cum += float(forecast[i])
            cumulative.append(cum)
        point = tuple(cumulative[h - 1] for h in horizons)
        return ForecastResult(horizons=tuple(horizons), point=point)
