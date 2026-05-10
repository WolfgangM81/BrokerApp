# Claude / AI Agent Context

This file gives AI coding agents the context needed to work productively in
this repo without re-deriving project conventions every session.

## Project goal

BrokerApp is an **ML-powered stock-forecast + decision-support tool** for
personal use across multiple asset classes (stocks US/EU, ETFs, crypto,
FX/commodities) and multiple horizons (intraday → 6 months). Self-hosted in a
homelab k8s cluster, multi-user via Authentik OIDC.

It is **not** a trading bot. The product is a forecasting + research +
decision-support UI: charts, multi-horizon forecasts with confidence bands,
walk-forward backtests, paper trading, risk metrics, alerts.

## Non-goals

- Real-time tick streaming / sub-second latency / HFT
- Order execution / broker integrations (kept explicitly out of scope for now)
- Public SaaS — this stays inside the homelab behind ZeroTier

## Architecture rules

1. **API-first.** All product features go through FastAPI; the web UI is one
   client among many. Never put business logic in `apps/web/`.
2. **OpenAPI is the contract.** TypeScript types are generated from the
   FastAPI OpenAPI spec, not hand-written.
3. **Time is UTC everywhere internally.** Timezone conversion happens at the
   UI boundary only. Bars are stored in UTC in TimescaleDB hypertables.
4. **No look-ahead bias.** All ML features must be computable with information
   available at the prediction time `t`. Walk-forward CV is mandatory.
5. **Determinism.** Set seeds. Pin versions. Reproducible models.
6. **Multi-asset by design.** Schemas, APIs, and models accept asset + horizon
   as parameters. Avoid per-asset hardcoding.
7. **Decision over prediction.** The product is "should I act?" — not "what's
   the price?". Always pair forecasts with confidence + backtest evidence.

## Tech-stack summary

See [`README.md`](./README.md) for the table. Key versions:

- Python 3.12, `uv` for env + workspace
- Node 22, `pnpm` 9 for workspace
- FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic
- Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui
- TimescaleDB (Postgres 16 + Timescale extension)
- Celery + Redis (broker + cache)
- MLflow + MinIO (artifact store)
- Authentik OIDC for auth

## Coding conventions

### Python
- Format: `ruff format`. Lint: `ruff check`. Types: `mypy --strict`.
- 4-space indent, line length 100.
- Public functions get type hints. No `Any` unless justified.
- `structlog` for logging — never `print`, never plain `logging` in app code.
- Pydantic v2 models for all I/O boundaries.
- SQLAlchemy 2.0 style (`select(...)`, `session.execute(...)`).
- **DataFrames: Polars is primary** (see ADR-0007). Pandas only at library
  boundaries (yfinance / ccxt input, sklearn / LightGBM input). Convert at
  the boundary, never propagate pandas frames through in-house code.
- **Indicators: TA-Lib** (see ADR-0007). Call via numpy arrays
  (`talib.SMA(close.to_numpy(), 20)`); thin Polars wrappers live in
  `ml/features/indicators.py` (Phase 3+).

### TypeScript
- Format: `prettier`. Lint: `eslint`.
- 2-space indent, line length 100, double quotes, trailing commas.
- Strict TS, no `any`. Use generated `api-client` types.
- Server Components by default in `apps/web/`; mark client with `"use client"` deliberately.

### Tests
- Backend: `pytest` + `pytest-asyncio`. Coverage target 70%, more on
  business logic (forecast/backtest/risk).
- Frontend: `vitest` (units), `playwright` (E2E against docker-compose).
- ML: deterministic tests against fixture datasets in `ml/tests/fixtures/`.

### Commits
- Conventional Commits: `feat(api): ...`, `fix(web): ...`, `chore: ...`,
  `docs(adr): ...`, etc.
- Keep commits small and reviewable. Prefer multiple commits over one big one.

## Phase plan

Phase 0: Foundation — repo skeleton, tooling, CI/CD bones. ✅
Phase 1 (current): Data backbone — schemas, ingest, market calendars,
  versioned API, Authentik auth.
Phase 2: UI + Auth — Next.js + Authentik OIDC + watchlists/charts.
Phase 3: Forecast baseline — Naive, ARIMA, LightGBM, walk-forward backtest.
Phase 4: Operations — Helm to cluster, monitoring, alerts, backups.
Phase 5: Advanced ML — TFT/N-HiTS, sentiment, macro, ensembles, SHAP, drift.
Phase 6: Risk + Portfolio — position sizing, multi-asset risk metrics.
Phase 7: Mobile (when needed) — Expo/React Native.

Stay within the current phase unless explicitly told otherwise. Do not write
TFT code in Phase 1. Do not skip Operations to chase ML features.

## Phase-1 cheat sheet (for fast onboarding)

- `services/db/` is the shared SQLAlchemy package. Both `apps/api` (async)
  and `services/ingest` (sync) depend on it. Don't define models elsewhere.
- All API routes live under `/v1/...`. Health, metrics, OpenAPI live at
  the root.
- Errors: raise `APIError(...)` or use the helpers (`not_found`,
  `conflict`, …) — they produce RFC 7807 Problem responses (ADR-0008).
- Auth dependencies: `current_user` (JWT against Authentik JWKS),
  `require_admin` (Authentik group), `require_worker` (internal token).
- Pagination: cursor-based, `Page[T]` + `encode_cursor` / `decode_cursor`.
- Bars schema: hypertable in `market.bars`, primary key
  `(asset_id, time, granularity)`. Idempotency = unique constraint.
- Asset → adapter mapping lives in `services/ingest/src/ingest/sources/
  registry.py`. New source = new module + register here.
- Adding to a watchlist triggers `ingest.backfill_asset` via Celery
  (`_trigger_backfill` in routes/watchlists.py).

## Things to avoid

- **Per-asset code paths.** If you find yourself writing `if asset == "BTC"`,
  generalize via asset-class metadata.
- **Ad-hoc time math.** Use `exchange_calendars` for market hours, `pandas`
  tz-aware timestamps. Never naive datetimes.
- **Look-ahead in features.** Anything using future data is a bug, even if it
  looks accidental. Tests must catch this.
- **Hidden mutable state in workers.** Celery tasks must be pure with respect
  to inputs.
- **Premature abstraction.** Build the second concrete case first; abstract
  only when the duplication is real.
- **Files at the root.** Everything goes in `apps/`, `services/`,
  `packages/`, `ml/`, `infra/`, `docs/`. Root holds only config.
