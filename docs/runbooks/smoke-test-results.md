# Smoke-Test results — Phase 8.5

Pre-cluster smoke run from the dev environment. The goal was to catch
"this won't even build/lint/type-check" failures before touching the
homelab. **12 real bugs were found and fixed**; everything that could
be tested without Docker / Kubernetes is now green.

## TL;DR

| Smoke | Status | Counts |
|---|---|---|
| Python lint (ruff) | ✅ | 0 issues across 89 files |
| Python format (ruff format --check) | ✅ | 89/89 already formatted |
| Python tests — `apps/api` | ✅ | 23/23 |
| Python tests — `services/ingest` | ✅ | 7/7 |
| Python tests — `services/notifier` | ✅ | 1/1 |
| Python tests — `ml/` | ✅ | 32/32 |
| **Python total** | ✅ | **63/63** |
| `pnpm install` (workspace) | ✅ | clean (2 expected peer-warns) |
| TS typecheck — `apps/web` | ✅ | 0 errors |
| TS typecheck — `apps/mobile` | ✅ | 0 errors |
| TS typecheck — `packages/api-client` | ✅ | 0 errors |
| Vitest — `apps/web` | ✅ | 1/1 |
| `helm lint` — all 7 charts (incl. umbrella) | ✅ | 0 failures |
| `helm template brokerapp infra/helm/umbrella` | ✅ | 17 resources rendered (906 lines) |
| `kubeconform -strict -k8s 1.31` | ✅ | 16/17 valid, 1 skipped (CRD, expected) |
| Docker images (Dockerfile.* builds) | ⏳ | N/A — no Docker daemon in dev env |
| docker-compose stack | ⏳ | N/A — no Docker daemon in dev env |
| DB integration tests (TimescaleDB) | ⏳ | N/A — needs running TimescaleDB |

## Bugs found and fixed

### #1 Test setup — `ASGITransport(raise_app_exceptions=True)` masked the catch-all handler

**Where:** `apps/api/tests/test_errors.py`
**Symptom:** `test_unhandled_exception_is_not_leaked` failed because
`httpx.ASGITransport` re-raises app exceptions by default, bypassing our
registered `Exception` handler.
**Fix:** Pass `raise_app_exceptions=False` to `ASGITransport` so the
generic handler is exercised the way uvicorn would in production.

### #2 Phase-0 test still expected `/readyz → ok` after Phase 1 added DB/Redis checks

**Where:** `apps/api/tests/test_health.py`
**Symptom:** `test_readyz_returns_ok` failed with `'degraded' != 'ok'`
because Phase-1's `/readyz` actually pings Postgres + Redis and the
unit-test env has neither.
**Fix:** Test now asserts the status is in `{"ok", "degraded"}` and
that both `postgres` and `redis` checks are reported.

### #3 `--strict-config` + `asyncio_mode = "auto"` broke notifier tests

**Where:** `services/notifier/pyproject.toml`
**Symptom:** `pytest.PytestConfigWarning: Unknown config option:
asyncio_mode` because `pytest-asyncio` wasn't a dev dep and the root
`pyproject.toml` has `--strict-config`.
**Fix:** Add `pytest-asyncio>=0.24.0` to the notifier's dev extras.

### #4 `shap` resolved an ancient `llvmlite==0.36.0` (Python 3.10-only)

**Where:** `ml/pyproject.toml`
**Symptom:** `uv sync --package brokerapp-ml`:
`RuntimeError: Cannot install on Python version 3.12.3; only versions
>=3.6,<3.10 are supported` for llvmlite.
**Fix:** Pin floors `numba>=0.60.0` and `llvmlite>=0.43.0` so the
resolver picks a Python-3.12-compatible chain.

### #5 Same `asyncio_mode` issue in `ml/`

**Where:** `ml/pyproject.toml`
**Fix:** Same fix as #3 — `pytest-asyncio>=0.24.0` in dev extras.

### #6 `NameError: name 'Sequence' is not defined` at module-level

**Where:** `ml/src/brokerapp_ml/backtests/engine.py`
**Symptom:** `Sequence` was imported only inside `TYPE_CHECKING` but
referenced at runtime via a `_ = Sequence` "ruff-silencer".
**Fix:** Removed both the import and the silencer line; engine.py
doesn't need `Sequence` at runtime.

### #7 `lightweight-charts` v4 API in code, but Phase-2 chose v5 syntax

**Where:** `apps/web/src/components/charts/asset-chart.tsx` +
`apps/web/package.json`
**Symptom:** TS errors: `Module '"lightweight-charts"' has no exported
member 'CandlestickSeries'` and `Property 'addSeries' does not exist
on type 'IChartApi'. Did you mean 'addBarSeries'?`
**Fix:** Bumped `lightweight-charts` to `^5.0.5` — the chart code was
already written against the v5 API (`chart.addSeries(CandlestickSeries,
…)`), only the package.json was on v4.

### #8 next-intl `Link href={{ pathname, params }}` doesn't pass TS strict checking

**Where:**
- `apps/web/src/app/[locale]/watchlists/watchlists-client.tsx`
- `apps/web/src/app/[locale]/watchlists/[id]/watchlist-detail-client.tsx`

**Symptom:** TS2353 — `params` not a known property of `UrlObject`.
**Fix:** Use string-interpolated hrefs (`/watchlists/${wl.id}`,
`/assets/${m.asset_id}`) — loses typed-route safety on these two
spots but compiles cleanly. The runtime behavior is identical.

### #9 `Omit<RequestInit, "body">` then re-using `init.body`

**Where:** `packages/api-client/src/index.ts`
**Symptom:** TS2339 — `Property 'body' does not exist on type
'RequestInitWithJson'`.
**Fix:** Removed the `Omit` so `RequestInit` still carries `body` as
an optional property.

### #10 Vitest picked up Playwright e2e specs

**Where:** `apps/web/vitest.config.ts`
**Symptom:** `vitest run` collected `e2e/signin.spec.ts` and crashed
inside Playwright's `test()` registration.
**Fix:** `include: ["src/**/*.{test,spec}.{ts,tsx}"]` plus
`exclude: ["node_modules", ".next", "out", "e2e/**"]`.

### #11 + #12 Helm: duplicate `app.kubernetes.io/component` key on beat Deployments

**Where:**
- `infra/helm/worker/templates/deployment.yaml`
- `infra/helm/forecast-worker/templates/deployment.yaml`

**Symptom:** `kubeconform` failure:
`line 14: key "app.kubernetes.io/component" already set in map` — the
beat metadata included the full `<chart>.labels` (which carries
`component: worker`) **and** then appended a second
`app.kubernetes.io/component: beat` line.
**Fix:** Added dedicated `worker.beatLabels` /
`worker.beatSelectorLabels` (and the forecast-worker counterparts) in
each `_helpers.tpl`; the beat block now uses those instead of trying
to override the worker labels.

## What still isn't validated

These four classes of smoke test need a real cluster / Docker daemon
and are documented in [`docs/runbooks/95-deploy.md`](./95-deploy.md)
as part of first-deploy verification:

- **Docker image builds** (Dockerfile.api / .web / .worker / .forecast /
  .migrate). Likely sources of friction: TA-Lib compile (~2 min,
  deterministic), pnpm install inside the Next standalone build.
- **`docker compose up`** (local TimescaleDB / Redis / MinIO / MLflow).
- **Alembic migrations against a real TimescaleDB** — the hypertable
  hook + autogenerate combo (ADR-0014) is unit-tested for shape but
  not against the live DB. The integration tests in
  `services/db/tests/test_integration.py` are gated on
  `BROKERAPP_DB_INTEGRATION_URL` and run automatically in CI.
- **End-to-end** — Authentik OIDC roundtrip, yfinance ingest, forecast
  task, mobile Expo bundle.

## Bottom line

Everything that **doesn't need a cluster** is green. The 12 bugs above
would have blocked the first CI pipeline run; they're fixed and pushed.
First-cluster bring-up will still find a few more issues (yfinance API
quirks, Authentik JWKS specifics, Darts API changes — these can't be
caught by static analysis) but the surface is now much smaller.
