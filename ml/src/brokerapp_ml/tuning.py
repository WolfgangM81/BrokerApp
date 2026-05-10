"""Optuna-based hyperparameter tuning for LightGBM.

The objective minimizes RMSE on a single walk-forward fold (the most
recent test_size bars). For per-asset-class tuning, run this once per
class and persist the best params alongside the model in MLflow.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import polars as pl

from brokerapp_ml.backtests.metrics import regression_metrics
from brokerapp_ml.cv import walk_forward
from brokerapp_ml.features.indicators import FEATURE_COLUMNS, build_features
from brokerapp_ml.models.lightgbm_model import LightGBMForecaster

if TYPE_CHECKING:
    pass


def tune_lightgbm(
    bars: pl.DataFrame,
    *,
    horizon: int = 5,
    n_trials: int = 25,
    initial_train: int = 252,
    test_size: int = 21,
    timeout_seconds: int | None = 1800,
    seed: int = 42,
) -> Mapping[str, float | int | str]:
    """Return the best hyperparameters discovered by Optuna."""
    import optuna  # noqa: PLC0415

    feats = build_features(bars, horizons=(horizon,))
    splits = list(walk_forward(feats.height, initial_train=initial_train, test_size=test_size))
    if not splits:
        return {}

    last_split = splits[-1]
    train = feats.slice(last_split.train_index.start, len(last_split.train_index))
    test = feats.slice(last_split.test_index.start, len(last_split.test_index))
    target_col = f"target_log_return_h{horizon}"

    def objective(trial: optuna.trial.Trial) -> float:
        params: dict[str, object] = {
            "objective": "regression",
            "verbosity": -1,
            "n_estimators": trial.suggest_int("n_estimators", 100, 800),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 255),
            "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 10, 100),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
            "bagging_freq": trial.suggest_int("bagging_freq", 0, 10),
            "lambda_l2": trial.suggest_float("lambda_l2", 0.0, 5.0),
        }
        forecaster = LightGBMForecaster(feature_columns=FEATURE_COLUMNS, params=params)
        forecaster.fit(train, [horizon])
        preds: list[float] = []
        actuals: list[float] = []
        for i in range(test.height):
            window = feats.slice(0, last_split.train_index.stop + i)
            res = forecaster.predict(window, [horizon])
            actual = test[target_col][i]
            if actual is None:
                continue
            preds.append(float(res.point[0]))
            actuals.append(float(actual))
        return regression_metrics(actuals, preds)["rmse"]

    sampler = optuna.samplers.TPESampler(seed=seed)
    pruner = optuna.pruners.MedianPruner(n_warmup_steps=5)
    study = optuna.create_study(direction="minimize", sampler=sampler, pruner=pruner)
    study.optimize(objective, n_trials=n_trials, timeout=timeout_seconds)
    return dict(study.best_params)


__all__ = ["tune_lightgbm"]
