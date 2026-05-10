"""Forecast-evaluation metrics."""

from __future__ import annotations

import math

from brokerapp_ml.backtests.metrics import directional_metrics, regression_metrics


def test_regression_metrics_perfect_prediction() -> None:
    m = regression_metrics([0.01, -0.02, 0.005], [0.01, -0.02, 0.005])
    assert m["mae"] == 0.0
    assert m["rmse"] == 0.0
    assert m["bias"] == 0.0


def test_regression_metrics_handles_empty() -> None:
    m = regression_metrics([], [])
    assert math.isnan(m["mae"])


def test_directional_metrics_full_hit() -> None:
    m = directional_metrics([0.01, -0.02, 0.005], [0.02, -0.01, 0.001])
    assert m["hit_rate"] == 1.0


def test_directional_metrics_zero_hit() -> None:
    m = directional_metrics([0.01, -0.01, 0.01], [-0.01, 0.01, -0.01])
    assert m["hit_rate"] == 0.0
