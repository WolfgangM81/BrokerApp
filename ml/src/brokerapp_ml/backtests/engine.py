"""Walk-forward backtest engine.

The engine is intentionally not vectorbt-backed in Phase 3 — vectorbt's
strategy/portfolio API is overkill for "fit a forecaster, see how its
log-return predictions agree with realized values". When Phase 5 adds
portfolio simulation we can swap to vectorbt without changing the
forecaster contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import polars as pl

from brokerapp_ml.backtests.metrics import directional_metrics, regression_metrics
from brokerapp_ml.cv import assert_no_lookahead, walk_forward
from brokerapp_ml.features.indicators import build_features

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brokerapp_ml.models.base import Forecaster


@dataclass(frozen=True, slots=True)
class BacktestResult:
    horizon: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    metrics: dict[str, float]
    n_predictions: int


def walk_forward_backtest(
    bars: pl.DataFrame,
    forecaster: Forecaster,
    *,
    horizon: int = 5,
    initial_train: int = 252,
    test_size: int = 21,
    expanding: bool = True,
) -> BacktestResult:
    """Run an expanding-window walk-forward backtest at one horizon.

    Args:
        bars: OHLCV frame (Polars), monotonically increasing in `time`.
        forecaster: instance implementing `Forecaster`.
        horizon: prediction horizon in bars (matches feature `target_log_return_h{h}`).
        initial_train: bars in the first training window.
        test_size: bars per test fold (one prediction per bar).
    """
    feats = build_features(bars, horizons=(horizon,))
    assert_no_lookahead(feats)

    target_col = f"target_log_return_h{horizon}"
    n = feats.height

    y_true: list[float] = []
    y_pred: list[float] = []

    splits = list(
        walk_forward(
            n,
            initial_train=initial_train,
            test_size=test_size,
            expanding=expanding,
        ),
    )
    if not splits:
        return BacktestResult(
            horizon=horizon,
            train_start=datetime.min,
            train_end=datetime.min,
            test_start=datetime.min,
            test_end=datetime.min,
            metrics={"n": 0},
            n_predictions=0,
        )

    for split in splits:
        train_frame = feats.slice(split.train_index.start, len(split.train_index))
        test_frame = feats.slice(split.test_index.start, len(split.test_index))
        forecaster.fit(train_frame, [horizon])
        for i in range(test_frame.height):
            point = test_frame.slice(0, train_frame.height + i + 1).tail(1)
            actual = point[target_col][0]
            if actual is None:
                continue
            # Predict on the trailing window up to the *current* row; never
            # peek into the future.
            window = feats.slice(0, split.train_index.stop + i)
            res = forecaster.predict(window, [horizon])
            y_true.append(float(actual))
            y_pred.append(float(res.point[0]))

    metrics = {**regression_metrics(y_true, y_pred), **directional_metrics(y_true, y_pred)}
    metrics["n"] = float(len(y_true))

    times = feats["time"].to_list()
    first_train = times[splits[0].train_index.start]
    last_train = times[splits[0].train_index.stop - 1]
    first_test = times[splits[0].test_index.start]
    last_test = times[splits[-1].test_index.stop - 1]
    return BacktestResult(
        horizon=horizon,
        train_start=first_train,
        train_end=last_train,
        test_start=first_test,
        test_end=last_test,
        metrics=metrics,
        n_predictions=len(y_true),
    )


__all__ = ["BacktestResult", "walk_forward_backtest"]


# silence ruff
_ = Sequence
