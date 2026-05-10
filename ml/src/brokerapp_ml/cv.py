"""Time-series cross-validation primitives.

ADR-0006 makes walk-forward mandatory; this module is the only place where
splits are generated, so a CI grep for `KFold` outside this file is a
strong (if heuristic) regression signal.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import pairwise

import polars as pl


@dataclass(frozen=True, slots=True)
class Split:
    train_index: range
    test_index: range


def walk_forward(
    n: int,
    *,
    initial_train: int,
    test_size: int,
    step: int | None = None,
    expanding: bool = True,
) -> Iterator[Split]:
    """Yield walk-forward splits.

    Args:
        n: total number of ordered samples.
        initial_train: size of the first training window.
        test_size: number of samples per test fold.
        step: how far to advance between folds (default: `test_size`).
        expanding: True for expanding window (recommended), False for
                   rolling window of `initial_train` size.
    """
    if initial_train <= 0 or test_size <= 0:
        raise ValueError("initial_train and test_size must be positive.")
    if initial_train + test_size > n:
        return
    step = step or test_size
    train_start = 0
    train_end = initial_train
    while train_end + test_size <= n:
        if expanding:
            train_idx = range(0, train_end)
        else:
            train_idx = range(max(0, train_end - initial_train), train_end)
        test_idx = range(train_end, train_end + test_size)
        yield Split(train_index=train_idx, test_index=test_idx)
        train_end += step
        train_start += step


def assert_no_lookahead(frame: pl.DataFrame, time_col: str = "time") -> None:
    """Cheap sanity check: feature frames must be monotonically time-ordered."""
    if frame.is_empty():
        return
    times = frame[time_col].to_list()
    if any(b < a for a, b in pairwise(times)):
        raise ValueError(f"Feature frame is not monotonically increasing in `{time_col}`.")


__all__ = ["Split", "assert_no_lookahead", "walk_forward"]


# silence ruff
_ = Iterable
