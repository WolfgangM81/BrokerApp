"""PSI / KL drift sanity tests."""

from __future__ import annotations

import math

import numpy as np
from brokerapp_ml.drift import drift_report, kl_divergence, psi


def test_psi_zero_for_identical_samples() -> None:
    rng = np.random.default_rng(42)
    samples = rng.normal(size=1000)
    val = psi(samples, samples)
    assert abs(val) < 1e-6


def test_psi_grows_with_distribution_shift() -> None:
    rng = np.random.default_rng(1)
    ref = rng.normal(size=2000)
    far = rng.normal(loc=2.0, size=2000)
    assert psi(ref, far) > 0.25


def test_kl_zero_for_identical_samples() -> None:
    rng = np.random.default_rng(99)
    samples = rng.normal(size=500)
    val = kl_divergence(samples, samples)
    assert abs(val) < 1e-6


def test_drift_report_returns_both_metrics() -> None:
    rng = np.random.default_rng(7)
    ref = rng.normal(size=300)
    cur = rng.normal(loc=0.5, size=300)
    report = drift_report("close", ref, cur)
    assert report.name == "close"
    assert not math.isnan(report.psi)
    assert not math.isnan(report.kl)
