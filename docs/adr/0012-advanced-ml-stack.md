# ADR-0012: Advanced-ML stack — Darts, FRED, FinBERT-later, SHAP, Optuna

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

Phase 5 introduces deep-learning time-series models, exogenous (macro +
sentiment) features, ensembles, drift detection, and explainability.
Each of those has many serviceable libraries; we lock the choices to
avoid sprawl.

## Decision

| Concern | Library | Notes |
|---------|---------|-------|
| Deep-learning forecasters | **Darts** (TFT, N-HiTS) | Wraps PyTorch Lightning; supports global models on multiple series, which is what makes CPU-only training viable for our universe (ADR-0005). |
| Macro features | **FRED CSV endpoint** + custom Polars adapter | Free, anonymous, deterministic. JSON+API-key path supported via `FRED_API_KEY`. |
| News sentiment | **Stub now, FinBERT later** | The `SentimentScorer` interface + `RuleBasedSentimentScorer` ship now so the rest of the pipeline (aggregation, join-onto-bars, downstream features) is exercised end-to-end. The FinBERT swap is a single-file change. |
| Ensembles | **Weighted-average** (`EnsembleForecaster`) | Stacking with meta-learner is deferred until we have enough out-of-fold predictions to justify it. |
| Explainability | **LightGBM `pred_contrib`** (TreeSHAP) | Native, fast, identical to SHAP for tree models. Result is a `{feature: contribution}` dict persisted in `forecasts.explain`. |
| Drift | **PSI + KL divergence** | Hand-rolled in `brokerapp_ml.drift`; cluster jobs can wire these into Prometheus gauges in Phase 4+. |
| Hyperparameter tuning | **Optuna** with TPE + Median pruning | Walk-forward objective; budget is `n_trials * timeout`, never grid-search. |

## Consequences

**+** Each concern has exactly one home. Future contributors don't have
       to choose.
**+** All advanced models implement the same `Forecaster` ABC as the
       baselines, so the worker tasks don't need new code paths.
**−** Darts pulls in PyTorch (~1 GB image bloat). Acceptable for the
       worker image; not added to the API or web images.
**−** FRED is rate-limited; we cache the panel in MinIO when we hit
       limits (later phase).
