# BrokerApp

ML-powered stock forecast and decision-support tool. Self-hosted, multi-user,
multi-asset (stocks, ETFs, crypto, FX), multi-horizon forecasts with backtesting
and risk-aware decision metrics.

> ⚠️ **Disclaimer:** This is a personal research and decision-support tool. It
> does not provide investment advice. All forecasts come with uncertainty —
> models can and will be wrong. Use at your own risk.

## Status

**Phase 1 — Data backbone.** SQLAlchemy models, Alembic migrations
(TimescaleDB hypertable), Authentik-OIDC auth, RFC 7807 errors,
`/v1/assets`, `/v1/assets/{id}/bars`, `/v1/watchlists` (member-add
triggers Celery backfill), yfinance + ccxt adapters, exchange-calendar
gating, idempotent upserts. Phase 0 (foundation) is shipped.

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

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15, TypeScript, Tailwind, shadcn/ui, TanStack Query, TradingView Lightweight Charts |
| Backend  | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Workers  | Celery + Redis, Celery Beat |
| ML       | LightGBM/XGBoost, Darts/pytorch-forecasting (Phase 5), MLflow, Optuna, SHAP, vectorbt |
| Data     | TimescaleDB (hypertables + continuous aggregates), Redis, MinIO |
| Auth     | Authentik (OIDC) — verified via JWKS in API |
| Infra    | k8s (Homelab, 3× Lenovo m75q), Helm, Traefik, Longhorn, kube-prometheus-stack |
| CI/CD    | GitLab CI/CD → GitLab Container Registry → kubectl/helm |

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
