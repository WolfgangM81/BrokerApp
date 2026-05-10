# BrokerApp — Architecture

This document is the canonical, mid-level view of how BrokerApp is built. For
the *why* behind individual choices, see the
[Architecture Decision Records](./adr/). For day-to-day operations, see
[`runbooks/`](./runbooks/).

---

## 1. System overview

```
                  ┌──────────────────────────────────────────────┐
                  │                  Clients                      │
                  │  Web (Next.js)   Mobile (later)   CLI / Notebook│
                  └─────────────┬──────────────┬────────────────┘
                                │              │
                          OIDC (Authentik)  REST + WebSocket
                                │              │
                                ▼              ▼
                    ┌──────────────────────────────────────────────┐
                    │            FastAPI Gateway                    │
                    │  - JWT verify (Authentik JWKS)                │
                    │  - OpenAPI as the contract                    │
                    │  - Rate-limit, audit log                      │
                    └────┬───────────────┬───────────────┬──────────┘
                         │               │               │
              ┌──────────▼─────┐ ┌───────▼──────┐ ┌──────▼─────────┐
              │ Market Data    │ │ Forecast     │ │ Backtest       │
              │ Service (ingest│ │ Engine       │ │ Engine         │
              │ Celery worker) │ │ (inference + │ │ (vectorbt,     │
              │                │ │  training)   │ │  walk-forward) │
              └──────┬─────────┘ └──────┬───────┘ └──────┬─────────┘
                     │                  │                │
                     └────────┬─────────┴────────┬───────┘
                              │                  │
                  ┌───────────▼────────┐   ┌─────▼──────────┐
                  │ TimescaleDB        │   │ MLflow Tracking│
                  │  - bars (hypertbl) │   │  + Model Reg.  │
                  │  - app metadata    │   │  + Artifacts   │
                  │ Postgres schemas   │   │   (MinIO)      │
                  │ Redis (cache/queue)│   └────────────────┘
                  └────────────────────┘
                              │
                  ┌───────────▼────────┐
                  │ Notifier (ntfy.sh) │
                  │  - alerts          │
                  │  - daily digest    │
                  └────────────────────┘
```

## 2. Components

### 2.1 `apps/api` — FastAPI Gateway

Entry point for all clients. Verifies Authentik JWTs against the JWKS endpoint,
exposes OpenAPI from which a typed TypeScript client is generated. All business
logic that needs persistence goes through services (DB-backed) and emits jobs
to Celery for async work.

### 2.2 `apps/web` — Next.js Frontend

App-Router-based Next.js. Server Components by default; client components only
where needed (interactive charts, forms with optimistic updates). State via
TanStack Query. Auth via Auth.js v5 with Authentik OIDC.

### 2.3 `services/ingest` — Market Data Workers

Celery workers that periodically pull bars from data sources (yfinance, ccxt,
later Polygon/Twelve Data). Adapters live behind a `MarketDataSource` interface
so the source is swappable. Respect market calendars via `exchange_calendars`.

### 2.4 `services/forecast` — ML Service

Two responsibilities, separated as Celery task groups:
- **Training:** scheduled retrains, hyperparameter sweeps via Optuna,
  walk-forward backtests. Models registered in MLflow.
- **Inference:** serve forecasts on-demand and on schedule, persist results in
  the `forecasts` table for historical evaluation.

### 2.5 `services/notifier` — Alerts

Subscribes to internal events (forecast-threshold-crossed, drift-detected,
backtest-degraded) and pushes via ntfy.sh.

### 2.6 `packages/api-client` — Generated TS Client

Auto-generated from FastAPI OpenAPI via `openapi-typescript`. Single source of
truth for request/response types between back-end and front-end.

### 2.7 `packages/ui` — Shared React Components

shadcn/ui-based primitives, charts wrappers, status badges, etc.

### 2.8 `ml/` — Research & Models

Notebooks, feature engineering, model definitions, backtests. `ml/` is a
Python workspace member. Promotion path: notebook → `ml/features/` →
`services/forecast/` once stable.

## 3. Data architecture

### 3.1 Storage

- **TimescaleDB** (Postgres 16 + Timescale extension): bars stored as a
  hypertable partitioned on `time`. Continuous aggregates roll 5-minute bars
  up to 15m / 1h / 1d for fast chart queries.
- **Postgres** (same instance, separate schemas): app metadata — `users`,
  `assets`, `watchlists`, `forecasts`, `backtests`, `models`, `trades`,
  `paper_portfolios`.
- **Redis:** Celery broker + cache for hot quotes + rate-limit counters.
- **MinIO:** MLflow artifact store + nightly DB backups.

### 3.2 Time and timezones

All timestamps in storage are **UTC**. Timezone conversion is a UI-boundary
concern. Market hours are decided per-asset-class via `exchange_calendars`
(NYSE, XETRA, …) with a 24/7 calendar for crypto.

### 3.3 Corporate actions

We use yfinance's adjusted close where available. Splits and dividends are
explicitly tested against fixtures. **Survivorship-bias-aware backtests**
require point-in-time index membership and are deferred to Phase 6.

## 4. ML architecture

### 4.1 Modeling strategy

- **Phase 1 baselines:** Naive (last-value), ARIMA, LightGBM with technical
  indicators. These define the "must beat" bar.
- **Phase 5 advanced:** Global TFT / N-HiTS via Darts / pytorch-forecasting,
  trained once across many assets (cross-learning), small enough to train on
  CPU overnight on the 3-node cluster.

### 4.2 Validation

- **Walk-forward CV** is mandatory. No naive K-fold on time series.
- **Purged K-Fold** (López de Prado) for hyperparameter selection where
  applicable.
- All splits respect chronology; no information from `t' > t` may inform a
  prediction for `t`.
- Determinism: seeds set, versions pinned.

### 4.3 Tracking & registry

- **MLflow** logs every run: parameters, metrics (MAE, RMSE, hit-rate,
  Sharpe, max-DD), artifacts (model, feature schema), tags (asset, horizon,
  data window).
- Models are registered with stages: `Staging` → `Production` → `Archived`.
- Production inference loads only `Production`-stage models.

### 4.4 Drift & retrains

- Rolling-window backtest performance is computed nightly; degradation past a
  threshold triggers a retrain.
- Feature drift (PSI, KL divergence) is computed nightly per feature; large
  drifts surface in Grafana.

### 4.5 Explainability

Forecasts come with SHAP values for the top-K features. The UI surfaces these
as "why this forecast?" — non-negotiable for a decision-support tool.

## 5. Auth & multi-tenancy

- **Authentik** is the identity provider (already running in homelab).
- Web logs in via Auth.js v5 (OIDC). API verifies access tokens against
  Authentik's JWKS — stateless on the API side.
- Every domain table has a `user_id` foreign key (or a `scope: 'global'`
  marker for shared assets). RBAC is read off Authentik group claims.

## 6. Deployment

### 6.1 Cluster

- 3× Lenovo m75q (Ryzen 5 PRO 3400GE, 32 GB RAM each), CPU-only.
- Access via ZeroTier; internal domain `*.orbiter`.
- StorageClass: Longhorn (replicated PVCs).
- Ingress: Traefik (to be installed).
- Monitoring: kube-prometheus-stack + Loki (to be installed).
- Secrets: GitLab CI variables (sourced from Vault) → templated into k8s
  Secrets at deploy time.

### 6.2 Pipeline

GitLab CI/CD:
1. **Lint** — ruff, mypy, eslint, prettier
2. **Test** — pytest, vitest, playwright
3. **Build** — Docker images for `api`, `web`, `worker`; pushed to GitLab
   Container Registry
4. **Deploy** — `helm upgrade` to k8s namespace `brokerapp`

### 6.3 Hostnames (`.orbiter`)

| Host | Service |
|------|---------|
| `brokerapp.orbiter` | Web |
| `api.brokerapp.orbiter` | API |
| `mlflow.brokerapp.orbiter` | MLflow UI |
| `flower.brokerapp.orbiter` | Celery Flower (optional) |
| `grafana.brokerapp.orbiter` | Grafana (or shared cluster Grafana) |

## 7. Security & compliance

- All HTTP traffic terminated at Traefik with TLS (internal CA via
  cert-manager).
- API rate-limited (slowapi) per user.
- Audit log table for sensitive actions (trade entries, paper trade resets,
  model promotions).
- Disclaimer banner in UI: "not investment advice".
- No PII beyond Authentik-managed identity. No payment data.

## 8. Phases

| Phase | Goal |
|-------|------|
| **0** | Repo skeleton, tooling, CI bones ✅ |
| **1** | Data backbone — schemas, ingest, calendars, API + tests ✅ |
| **2** | UI + Auth — Next.js + Authentik OIDC end-to-end ✅ |
| **3** | Forecast baseline + walk-forward backtest, UI integration ✅ |
| **4** | Operations — Helm to cluster, monitoring, alerting, backups ✅ |
| **5** | Advanced ML — TFT/N-HiTS, sentiment, macro, drift, SHAP ✅ |
| **6** | Risk + Portfolio — sizing, multi-asset risk, paper trading polish (current) |
| **7** | Mobile (when needed) — Expo / React Native |

We do not skip phases. Each phase ends with an explicit acceptance check.

## 9. Conventions

- Conventional Commits.
- ADRs in `docs/adr/` for any architecturally significant decision (see
  ADR-0001 for the meta-process).
- One PR per logical change; small commits within.
- `CLAUDE.md` is canonical for AI-agent context; keep it in sync with this
  document for human readers.
