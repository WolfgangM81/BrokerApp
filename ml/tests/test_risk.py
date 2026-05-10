"""Risk metrics + sizing rules contract."""

from __future__ import annotations

import math

import pytest
from brokerapp_ml.risk.metrics import (
    cvar,
    max_drawdown,
    portfolio_metrics,
    sharpe_ratio,
    sortino_ratio,
    var,
)
from brokerapp_ml.risk.sizing import (
    fixed_fractional,
    kelly_fraction,
    vol_target,
)
from brokerapp_ml.risk.stops import atr_stop, fixed_pct_stop


def test_sharpe_zero_for_zero_variance() -> None:
    assert sharpe_ratio([0.01, 0.01, 0.01]) == 0.0


def test_sharpe_positive_for_positive_drift() -> None:
    rng = [0.001, 0.002, 0.003, 0.001, 0.002]
    assert sharpe_ratio(rng) > 0


def test_max_drawdown_negative_for_drop() -> None:
    returns = [0.05, -0.1, -0.05, 0.02]
    dd = max_drawdown(returns)
    assert dd < 0


def test_var_and_cvar_align() -> None:
    returns = [-0.05, -0.04, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04]
    v = var(returns, alpha=0.1)
    c = cvar(returns, alpha=0.1)
    # CVaR is at least as bad as VaR.
    assert c >= v >= 0


def test_kelly_clamps_negative_edge() -> None:
    # 50/50 with 1:1 payoff has zero edge -> 0.
    assert kelly_fraction(0.5, 1.0) == 0.0


def test_kelly_capped() -> None:
    # 90/10 with 5:1 payoff has huge edge but cap=0.25.
    assert kelly_fraction(0.9, 5.0, cap=0.25) == pytest.approx(0.25)


def test_kelly_rejects_invalid_prob() -> None:
    assert kelly_fraction(-0.1, 1.0) == 0.0
    assert kelly_fraction(1.1, 1.0) == 0.0


def test_fixed_fractional_basic() -> None:
    # Risk 1% per trade with a 5% stop -> 1/5 = 0.2 of equity.
    assert fixed_fractional(0.01, 0.05) == pytest.approx(0.2)


def test_fixed_fractional_capped_at_one() -> None:
    assert fixed_fractional(0.5, 0.05) == 1.0


def test_vol_target_inverse_to_vol() -> None:
    # If forecast vol annualises to exactly target, we go fully invested.
    daily = 0.15 / math.sqrt(252)
    assert vol_target(daily, 0.15, cap=1.0) == pytest.approx(1.0)


def test_atr_stop_long_geometry() -> None:
    rec = atr_stop(100.0, 2.0, atr_multiple=2.0, rr=2.0, side="long")
    assert rec.stop_loss == 96.0
    assert rec.take_profit == 108.0


def test_fixed_pct_stop_short_geometry() -> None:
    rec = fixed_pct_stop(100.0, stop_pct=0.05, take_profit_pct=0.1, side="short")
    assert rec.stop_loss == 105.0
    assert rec.take_profit == 90.0


def test_portfolio_metrics_returns_struct() -> None:
    rng = [0.001, -0.002, 0.003, 0.001, -0.001, 0.002]
    m = portfolio_metrics(rng)
    assert hasattr(m, "sharpe")
    assert hasattr(m, "var_95")
    assert hasattr(m, "cvar_95")
    assert m.var_95 >= 0


def test_sortino_handles_no_downside() -> None:
    # All-positive returns -> no downside std -> 0 by convention.
    assert sortino_ratio([0.01, 0.02, 0.03]) == 0.0
