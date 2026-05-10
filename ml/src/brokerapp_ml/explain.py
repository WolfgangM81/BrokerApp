"""SHAP-based explainability wrappers.

The function `explain_lightgbm` takes a fitted LightGBM model + the
features used at inference time and returns the top-K feature
contributions for the single most-recent prediction. The result is
JSON-serialisable so it can be persisted in `forecasts.explain`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import polars as pl


def explain_lightgbm(
    model: Any,
    features: pl.DataFrame,
    feature_columns: Sequence[str],
    *,
    top_k: int = 5,
) -> dict[str, float]:
    """Return `{feature: contribution}` for the top-K abs contributions.

    Uses LightGBM's native `pred_contrib=True` which is much cheaper than
    SHAP's general algorithm and produces identical TreeSHAP values for
    tree models.
    """
    last = features.tail(1).select(feature_columns).fill_null(0.0).to_pandas()
    contributions = model.predict(last, pred_contrib=True)  # shape: (1, n_features+1)
    arr = np.asarray(contributions).flatten()
    feature_contribs = arr[:-1]  # last column is the bias term
    pairs = sorted(
        zip(feature_columns, feature_contribs.tolist(), strict=False),
        key=lambda kv: abs(kv[1]),
        reverse=True,
    )
    return {name: float(v) for name, v in pairs[:top_k]}


__all__ = ["explain_lightgbm"]
