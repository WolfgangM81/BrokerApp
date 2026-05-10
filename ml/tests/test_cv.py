"""Walk-forward CV contract."""

from __future__ import annotations

import polars as pl
import pytest
from brokerapp_ml.cv import assert_no_lookahead, walk_forward


def test_walk_forward_yields_chronological_splits() -> None:
    splits = list(walk_forward(100, initial_train=40, test_size=10))
    assert splits, "expected non-empty splits"
    for s in splits:
        assert s.train_index.start == 0  # expanding window
        assert s.train_index.stop == s.test_index.start
        assert s.test_index.stop - s.test_index.start == 10
    starts = [s.test_index.start for s in splits]
    assert starts == sorted(starts)
    assert splits[-1].test_index.stop <= 100


def test_walk_forward_rolling_window() -> None:
    splits = list(walk_forward(100, initial_train=30, test_size=5, expanding=False))
    for s in splits:
        assert len(s.train_index) == 30


def test_walk_forward_rejects_bad_args() -> None:
    with pytest.raises(ValueError):
        list(walk_forward(50, initial_train=0, test_size=5))


def test_walk_forward_returns_empty_when_no_room() -> None:
    assert list(walk_forward(20, initial_train=15, test_size=10)) == []


def test_assert_no_lookahead_passes_for_sorted() -> None:
    frame = pl.DataFrame({"time": [1, 2, 3, 4]})
    assert_no_lookahead(frame)


def test_assert_no_lookahead_raises_for_out_of_order() -> None:
    frame = pl.DataFrame({"time": [1, 3, 2, 4]})
    with pytest.raises(ValueError):
        assert_no_lookahead(frame)
