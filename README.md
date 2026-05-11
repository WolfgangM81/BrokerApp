# BrokerApp

ML-powered stock forecast and decision-support tool. Self-hosted, multi-user,
multi-asset (stocks, ETFs, crypto, FX), multi-horizon forecasts with backtesting
and risk-aware decision metrics.

> ⚠️ **Disclaimer:** This is a personal research and decision-support tool. It
> does not provide investment advice. All forecasts come with uncertainty —
> models can and will be wrong. Use at your own risk.

## Status

**All code phases (0–7) are in. Phase 8 (Hardening) is the last commit
before cluster bring-up.** What ships:

- **Foundation (0)** monorepo, CI/CD, lint/type/format toolchain
- **Data (1)** TimescaleDB hypertable, yfinance + ccxt ingest,
  Authentik-OIDC, RFC-7807 errors, `/v1/*` endpoints
- **UI (2)** Next.js 15, German default with English fallback
  (next-intl), TradingView Lightweight Charts
- **Forecast (3)** Naive / ARIMA / LightGBM with mandatory
  walk-forward backtests (ADR-0006)
- **Operations (4)** Helm charts for db/api/web/worker/forecast/backup,
  kube-prometheus-stack + Loki values, age-encrypted nightly backups
  with weekly restore-test
- **Advanced ML (5)** Darts (TFT / N-HiTS), FRED macro, sentiment stub
  (FinBERT swap-ready), ensembles, TreeSHAP, PSI/KL drift, Optuna
- **Risk + Portfolio (6)** Kelly / fixed-fractional / vol-target
  sizing, ATR + percentage stops, Sharpe / Sortino / VaR / CVaR /
  max-DD, paper-portfolio summary
- **Mobile (7)** Expo scaffold reusing the typed API client
- **Hardening (8)** dedicated `migrate` + `forecast` images, missing
  forecast-worker Helm chart, cert-manager internal CA, server-side
  `auth()` guards on every page, DB integration test suite, audit fixes

The repo is ready for the first `helm upgrade` against the homelab
cluster.

## Installation

Start at [`docs/runbooks/00-overview.md`](docs/runbooks/00-overview.md) —
the runbook walks from three blank Lenovo m75q boxes to a running
`https://brokerapp.orbiter`. The in-cluster pieces (Longhorn,
cert-manager, kube-prometheus-stack, Loki, MinIO) are installed by
the idempotent `infra/scripts/bootstrap-cluster.sh`; UI-clicks-only
steps (Authentik OIDC apps, Vault secrets, GitLab CI variables) are
documented step-by-step with exact field names.

See also [`docs/runbooks/restore.md`](docs/runbooks/restore.md) and
the ADRs in [`docs/adr/`](docs/adr/).

## Architecture (high-level)

```
Web (Next.js)  ─┐
Future Mobile  ─┼──▶  FastAPI Gateway  ──▶  Workers (Celery)
CLI/Notebook   ─┘            │                    │
                             ▼                    ▼
                       TimescaleDB          MLflow + MinIO
                       Redis / Postgres
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/adr/`](docs/adr/)
for the full picture and decisions.

## Tech stack (summary)

| Layer             | Choice                                                                                                         |
| ----------------- | -------------------------------------------------------------------------------------------------------------- |
| Frontend          | Next.js 15, TypeScript, Tailwind, shadcn/ui, TanStack Query, TradingView Lightweight Charts, next-intl (DE/EN) |
| Mobile            | Expo 52 + expo-router, expo-auth-session (OIDC), expo-secure-store, expo-notifications                         |
| Backend           | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic                                                       |
| Workers           | Celery + Redis, Celery Beat (separate `ingest` and `forecast` queues)                                          |
| ML                | Polars, LightGBM, XGBoost, statsmodels, Darts (TFT / N-HiTS), MLflow, Optuna, SHAP, TA-Lib                     |
| Macro / sentiment | FRED CSV, lexicon-based sentiment stub (FinBERT swap-ready)                                                    |
| Risk              | Sharpe / Sortino / VaR / CVaR / max-DD, Kelly / fixed-fractional / vol-target, ATR + pct stops                 |
| Data              | TimescaleDB (hypertable + continuous aggregates), Redis, MinIO                                                 |
| Auth              | Authentik (OIDC), JWKS-verified in API; `X-Internal-Token` for worker → API                                    |
| Infra             | k8s (Homelab, 3× Lenovo m75q), Helm umbrella, Traefik, Longhorn, cert-manager, kube-prometheus-stack, Loki     |
| CI/CD             | GitLab CI/CD → GitLab Container Registry (`gitlab.orbiter:5050`) → Helm upgrade                                |
| Backups           | nightly `pg_dump` + age-encrypted upload to MinIO, weekly restore-test CronJob (ADR-0010)                      |

## Repository layout

```
brokerapp/
├── apps/         # User-facing applications
│   ├── web/      # Next.js
│   └── api/      # FastAPI gateway
├── services/     # Background services
│   ├── ingest/   # Market data ingestion
│   ├── forecast/ # ML training + inference
│   └── notifier/ # ntfy.sh push notifications
├── packages/     # Shared TS libraries
│   ├── api-client/
│   └── ui/
├── ml/           # Notebooks, features, models, backtests
├── infra/        # Helm charts, Dockerfiles, Grafana dashboards
└── docs/         # Architecture, ADRs, runbooks
```

## Local development

Prerequisites:

- Node 22+ and `pnpm` 9+
- Python 3.12 and [`uv`](https://docs.astral.sh/uv/)
- Docker + Docker Compose
- (Recommended) `pre-commit`

```bash
# Install JS deps
pnpm install

# Install Python deps (creates .venv at root)
uv sync

# Start local infrastructure (TimescaleDB, Redis, MinIO)
docker compose up -d

# Install pre-commit hooks
pre-commit install

# Run everything in dev mode (api + web)
pnpm dev
```

## Branching

- `main` — production-deployable
- `claude/*` — agent-driven feature branches
- Phase-based development; see [`docs/ARCHITECTURE.md#phases`](docs/ARCHITECTURE.md#phases)

## License

Private project. All rights reserved.
