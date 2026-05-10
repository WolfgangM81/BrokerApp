# ADR-0005: CPU-only ML strategy

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

The cluster is 3× Lenovo m75q (Ryzen 5 PRO 3400GE, 4C/8T, 32 GB RAM each).
The integrated Vega 11 GPU has poor ROCm support and is not viable for
training. Total: 24 vCPU / 96 GB RAM, no GPUs.

We still want strong forecasting performance across multiple asset classes
and horizons.

## Decision

1. **Primary models are gradient-boosted trees** (LightGBM, XGBoost) on
   tabular features (technical indicators, lags, calendar features).
   Excellent CPU performance, often competitive with deep learning on
   typical financial time series.
2. **Deep learning where it pays off**, but with discipline:
   - Use **global** time-series models (one model trained on many series)
     via Darts / pytorch-forecasting — TFT, N-HiTS, N-BEATS.
   - Keep model sizes small (small hidden dims, few heads).
   - Restrict to overnight batch training, not on-demand.
3. **Distributed training across 3 nodes** via Ray when training time is the
   bottleneck.
4. **Inference is CPU-fine** for all expected model sizes — no concerns.
5. **Escape hatch:** if performance becomes the bottleneck, training-only
   bursts on Cloud GPU (RunPod, Vast.ai) or a single dedicated GPU node are
   easy to add — the architecture does not change, only the worker pool
   configuration.

## Consequences

**+** No GPU operational overhead, no driver/ROCm hell.
**+** Strong baselines (LightGBM) ship in Phase 3 with no GPU dependency.
**+** Costs stay at hardware electricity.
**−** SOTA deep-learning experimentation is slower; we accept long retrain
       cycles for advanced models.
**−** Hyperparameter sweeps are expensive — must use efficient search
       (Optuna with pruning) rather than brute-force grids.
