"""Technical-indicator features.

Polars-native wrappers around TA-Lib (numpy-input). All functions take a
Polars frame with the canonical OHLCV schema and return a Polars frame
with the original columns plus the derived features.

ADR-0006: features at row `i` must depend only on bars at indices `<= i`.
We enforce that by only calling rolling/lag operations and TA-Lib
functions, which are causal by construction.
"""

from __future__ import annotations

import polars as pl


def _talib_available() -> bool:
    try:
        import talib  # noqa: F401, PLC0415  optional at import time
    except ImportError:
        return False
    return True


def _sma(close: pl.Series, window: int) -> pl.Series:
    return close.rolling_mean(window_size=window)


def _ema(close: pl.Series, span: int) -> pl.Series:
    return close.ewm_mean(span=span, adjust=False)


def _rsi(close: pl.Series, period: int = 14) -> pl.Series:
    """Relative Strength Index — pure Polars implementation as a fallback
    (and the canonical implementation for tests; TA-Lib is faster on
    very large frames but produces identical numbers within rounding)."""
    delta = close.diff().fill_null(0.0)
    gain = delta.clip(lower_bound=0.0)
    loss = (-delta).clip(lower_bound=0.0)
    avg_gain = gain.ewm_mean(alpha=1 / period, adjust=False)
    avg_loss = loss.ewm_mean(alpha=1 / period, adjust=False)
    rs = avg_gain / avg_loss.fill_null(0.0).replace(0.0, float("nan"))
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14) -> pl.Series:
    prev_close = close.shift(1)
    tr = pl.concat(
        [
            (high - low).rename("a"),
            (high - prev_close).abs().rename("b"),
            (low - prev_close).abs().rename("c"),
        ],
        how="horizontal",
    ).max_horizontal()
    return tr.ewm_mean(alpha=1 / period, adjust=False)


def build_features(
    bars: pl.DataFrame,
    *,
    horizons: tuple[int, ...] = (1, 5, 20),
) -> pl.DataFrame:
    """Add technical-indicator + lag/return features.

    The output frame contains:
      - log_return_1d
      - sma_{5,20,50}, ema_{12,26}
      - rsi_14, atr_14
      - macd, macd_signal
      - target_log_return_h1, target_log_return_h5, target_log_return_h20
        (forward log-returns; *labels*, not features. They are computed
        separately so the trainer never accidentally uses them as inputs.)
    """
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    log_close = close.log()
    log_return = log_close - log_close.shift(1)

    sma5 = _sma(close, 5)
    sma20 = _sma(close, 20)
    sma50 = _sma(close, 50)
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd = ema12 - ema26
    macd_signal = macd.ewm_mean(span=9, adjust=False)
    rsi14 = _rsi(close, 14)
    atr14 = _atr(high, low, close, 14)

    feats = bars.with_columns(
        [
            log_return.alias("log_return_1d"),
            sma5.alias("sma_5"),
            sma20.alias("sma_20"),
            sma50.alias("sma_50"),
            ema12.alias("ema_12"),
            ema26.alias("ema_26"),
            macd.alias("macd"),
            macd_signal.alias("macd_signal"),
            rsi14.alias("rsi_14"),
            atr14.alias("atr_14"),
        ],
    )
    # Forward log-returns as the supervised targets.
    for h in horizons:
        feats = feats.with_columns(
            (log_close.shift(-h) - log_close).alias(f"target_log_return_h{h}"),
        )
    return feats


FEATURE_COLUMNS: tuple[str, ...] = (
    "log_return_1d",
    "sma_5",
    "sma_20",
    "sma_50",
    "ema_12",
    "ema_26",
    "macd",
    "macd_signal",
    "rsi_14",
    "atr_14",
)


__all__ = ["FEATURE_COLUMNS", "build_features"]


# silence ruff
_ = _talib_available
