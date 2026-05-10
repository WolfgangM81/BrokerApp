"""LightGBM regressor predicting forward log-returns at multiple horizons."""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from brokerapp_ml.features.indicators import FEATURE_COLUMNS
from brokerapp_ml.models.base import Forecaster, ForecastResult


class LightGBMForecaster(Forecaster):
    name = "lightgbm"

    def __init__(
        self,
        *,
        feature_columns: Sequence[str] = FEATURE_COLUMNS,
        params: dict[str, object] | None = None,
    ) -> None:
        self.feature_columns = tuple(feature_columns)
        self.params = params or {
            "objective": "regression",
            "learning_rate": 0.05,
            "num_leaves": 63,
            "min_data_in_leaf": 50,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbosity": -1,
            "n_estimators": 400,
        }
        self._models: dict[int, object] = {}

    def fit(self, features: pl.DataFrame, horizons: Sequence[int]) -> None:
        from lightgbm import LGBMRegressor  # noqa: PLC0415  optional dep

        for h in horizons:
            target = f"target_log_return_h{h}"
            available = features.drop_nulls(subset=[*self.feature_columns, target])
            if available.is_empty():
                continue
            x = available.select(self.feature_columns).to_pandas()
            y = available[target].to_pandas()
            model = LGBMRegressor(**self.params)
            model.fit(x, y)
            self._models[h] = model

    def predict(self, features: pl.DataFrame, horizons: Sequence[int]) -> ForecastResult:
        last = features.tail(1)
        x = last.select(self.feature_columns).fill_null(0.0).to_pandas()
        point: list[float] = []
        for h in horizons:
            model = self._models.get(h)
            if model is None:
                point.append(0.0)
                continue
            pred = float(model.predict(x)[0])  # type: ignore[attr-defined]
            point.append(pred)
        return ForecastResult(horizons=tuple(horizons), point=tuple(point))
