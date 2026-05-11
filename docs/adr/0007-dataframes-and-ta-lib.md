# ADR-0007: Polars as primary DataFrame; TA-Lib for indicators

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

We need to choose:

1. A canonical in-house DataFrame library for ingest, feature engineering,
   and backtesting code.
2. A technical-analysis library for indicator computation (SMA, EMA, RSI,
   MACD, Bollinger Bands, ATR, Stochastics, etc.).

DataFrame options considered:

- **Pandas** — industry default, huge ecosystem, but slow and memory-hungry
  for large frames; eager only.
- **Polars** — modern, Rust-based, lazy + eager, 10–100x faster on typical
  operations, lower memory footprint, strong type system, can read/write
  Parquet directly.
- Both — pragmatic but doubles the cognitive load.

TA-library options:

- **pandas-ta** — pandas-friendly but unmaintained (last release is a beta
  from years ago).
- **ta** — pure Python, active maintenance, simple install, covers the
  standard indicators with acceptable performance.
- **TA-Lib** — C library with Python bindings; the de-facto industry
  standard. Very fast, broadest indicator set. Requires `libta-lib` on the
  build host.

## Decision

1. **Polars is the primary in-house DataFrame library.** All ingest pipelines,
   feature engineering, and backtest code we write reads and writes Polars
   frames. The `MarketDataSource` interface returns a `polars.DataFrame`.

2. **Pandas is used only at library boundaries** — yfinance and ccxt return
   pandas frames; scikit-learn / LightGBM / XGBoost accept pandas (or
   numpy). Convert to Polars at the earliest possible boundary, convert
   back to pandas at the latest possible boundary.

3. **TA-Lib is the technical-analysis library**, despite the C-library
   build dependency. The dependency is contained to the Docker build for
   the worker image; local development uses `brew install ta-lib` (macOS)
   or `apt install libta-lib-dev` (Debian/Ubuntu). The performance and
   indicator breadth justify the install step.

## Consequences

**+** Polars is faster and uses less memory — both matter on the CPU-only
homelab cluster with 32 GB per node.
**+** TA-Lib's indicator set is comprehensive; no need to mix multiple
indicator libraries.
**+** Determinism: TA-Lib is widely used and trusted; results match
published references.
**−** The Polars/pandas boundary is real code we have to maintain. Helper
converters live in `services/ingest/src/ingest/convert.py` (and
analogous spots) — see code for conversion patterns.
**−** TA-Lib's C-library install is a real onboarding step; documented in
`README.md` and `Makefile`.
**−** Polars 1.x is still evolving; minor versions can introduce small
breaking changes. Mitigated by pinned upper bounds and Renovate
grouping.

## Notes for contributors

- Never write `df = pd.read_csv(...)` in new code; use `pl.read_csv(...)`
  (or `pl.scan_csv` for lazy).
- When passing data to scikit-learn / LightGBM, prefer
  `df.to_pandas()` at the boundary.
- TA-Lib functions take numpy arrays (`talib.SMA(close.to_numpy(), timeperiod=20)`),
  not DataFrames. A thin wrapper in `ml/features/indicators.py` will provide
  a Polars-native API in Phase 3.
