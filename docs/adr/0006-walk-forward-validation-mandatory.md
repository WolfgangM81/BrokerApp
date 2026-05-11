# ADR-0006: Walk-forward validation is mandatory

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

Naive cross-validation on time-series data leaks future information into
training (look-ahead bias) and produces optimistic, untrustworthy backtest
results. This is a famous and easy-to-make mistake; the entire credibility
of the product depends on avoiding it.

## Decision

1. **Walk-forward (expanding or rolling window) is the only validation
   protocol** for time-series models in this project. Naive K-fold on
   ordered time series is forbidden.
2. **Purged K-Fold with embargo** (López de Prado, _Advances in Financial
   Machine Learning_) is the protocol for hyperparameter selection where
   K-fold-style splits are needed.
3. **Feature-level guard:** any feature using information at time `t' > t`
   to predict `t` is a bug. We enforce this with:
   - A linter pattern check in CI (e.g. `shift(-…)`, `lookahead`,
     `future_*` substrings) — best-effort.
   - **Mandatory unit tests per feature** that assert the feature value at
     time `t` does not change when future bars are removed.
4. **Backtest reports always disclose** the validation protocol, train/test
   windows, and any data filtering. No "cherry-picked period" reports.

## Consequences

**+** Backtest numbers are trustworthy.
**+** Forces clean code — feature pipelines must be honest about timing.
**−** Slower experimentation; can't take cross-validation shortcuts.
**−** Some out-of-the-box CV helpers (e.g. sklearn's `KFold`) cannot be used
without wrapping; we provide our own splitters in `ml/features/`.
