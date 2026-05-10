"""Feature- and prediction-drift detection.

The two staples are PSI (Population Stability Index) for univariate
feature drift, and KL divergence for distributional shift on either
features or model predictions.

Both functions take *sample arrays*; binning is done internally so
callers don't need to share buckets.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

DEFAULT_BINS = 10


@dataclass(frozen=True, slots=True)
class DriftReport:
    name: str
    psi: float
    kl: float


def _histogram(samples: np.ndarray, edges: np.ndarray) -> np.ndarray:
    counts, _ = np.histogram(samples, bins=edges)
    p = counts.astype(float)
    if p.sum() == 0:
        return p
    p /= p.sum()
    # Avoid log(0) by adding a tiny epsilon — standard PSI/KL trick.
    p = np.clip(p, 1e-9, None)
    return p


def _shared_edges(reference: np.ndarray, current: np.ndarray, bins: int) -> np.ndarray:
    lo = float(min(reference.min(), current.min()))
    hi = float(max(reference.max(), current.max()))
    if hi == lo:
        hi = lo + 1.0
    return np.linspace(lo, hi, bins + 1)


def psi(
    reference: Iterable[float],
    current: Iterable[float],
    *,
    bins: int = DEFAULT_BINS,
) -> float:
    """Population Stability Index.

    Common interpretation: < 0.1 stable, 0.1 to 0.25 moderate drift,
    > 0.25 significant drift.
    """
    ref = np.asarray(list(reference), dtype=float)
    cur = np.asarray(list(current), dtype=float)
    if ref.size == 0 or cur.size == 0:
        return float("nan")
    edges = _shared_edges(ref, cur, bins)
    p = _histogram(ref, edges)
    q = _histogram(cur, edges)
    return float(np.sum((q - p) * np.log(q / p)))


def kl_divergence(
    reference: Iterable[float],
    current: Iterable[float],
    *,
    bins: int = DEFAULT_BINS,
) -> float:
    """KL(current || reference) — asymmetric by convention."""
    ref = np.asarray(list(reference), dtype=float)
    cur = np.asarray(list(current), dtype=float)
    if ref.size == 0 or cur.size == 0:
        return float("nan")
    edges = _shared_edges(ref, cur, bins)
    p = _histogram(ref, edges)
    q = _histogram(cur, edges)
    return float(np.sum(q * np.log(q / p)))


def drift_report(
    name: str,
    reference: Iterable[float],
    current: Iterable[float],
    *,
    bins: int = DEFAULT_BINS,
) -> DriftReport:
    return DriftReport(
        name=name,
        psi=psi(reference, current, bins=bins),
        kl=kl_divergence(reference, current, bins=bins),
    )


__all__ = ["DEFAULT_BINS", "DriftReport", "drift_report", "kl_divergence", "psi"]
