# Smoke-Test results — Phase 8.5

Pre-cluster smoke run from the dev environment. The goal was to catch
"this won't even build/lint/type-check" failures before touching the
homelab. **12 real bugs were found and fixed**; everything that could
be tested without Docker / Kubernetes is now green.

## TL;DR

| Smoke                                         | Status | Counts                                 |
| --------------------------------------------- | ------ | -------------------------------------- |
| Python lint (ruff)                            | ✅     | 0 issues across 89 files               |
| Python format (ruff format --check)           | ✅     | 89/89 already formatted                |
| Python tests — `apps/api`                     | ✅     | 23/23                                  |
| Python tests — `services/ingest`              | ✅     | 7/7                                    |
| Python tests — `services/notifier`            | ✅     | 1/1                                    |
| Python tests — `ml/`                          | ✅     | 32/32                                  |
| **Python total**                              | ✅     | **63/63**                              |
| `pnpm install` (workspace)                    | ✅     | clean (2 expected peer-warns)          |
| TS typecheck — `apps/web`                     | ✅     | 0 errors                               |
| TS typecheck — `apps/mobile`                  | ✅     | 0 errors                               |
| TS typecheck — `packages/api-client`          | ✅     | 0 errors                               |
| Vitest — `apps/web`                           | ✅     | 1/1                                    |
| `helm lint` — all 7 charts (incl. umbrella)   | ✅     | 0 failures                             |
| `helm template brokerapp infra/helm/umbrella` | ✅     | 17 resources rendered (906 lines)      |
| `kubeconform -strict -k8s 1.31`               | ✅     | 16/17 valid, 1 skipped (CRD, expected) |
| Docker images (Dockerfile.\* builds)          | ⏳     | N/A — no Docker daemon in dev env      |
| docker-compose stack                          | ⏳     | N/A — no Docker daemon in dev env      |
| DB integration tests (TimescaleDB)            | ⏳     | N/A — needs running TimescaleDB        |

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

> =3.6,<3.10 are supported`for llvmlite.
**Fix:** Pin floors`numba>=0.60.0`and`llvmlite>=0.43.0` so the
> resolver picks a Python-3.12-compatible chain.

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

---

## Second pass — mypy / ESLint / prettier / alembic-offline (Phase 8.6)

After the first smoke pass, extended verification covered every tool
the CI actually runs. **8 more bugs** found and fixed.

| Check | Status |
|---|---|
| `mypy --strict` — apps/api | ✅ |
| `mypy --strict` — services/db | ✅ |
| `mypy --strict` — services/ingest | ✅ |
| `mypy --strict` — services/notifier | ✅ |
| `pnpm -r run lint` (Next ESLint) | ✅ |
| `pnpm format:check` (prettier across whole repo) | ✅ (after 57 files were auto-formatted) |
| `alembic upgrade head --sql` (offline migration render) | ✅ — emits valid SQL through revision 0003 |
| Final `pytest` re-run after fixes — 63/63 | ✅ |
| Final `helm template + kubeconform` — 16/17 valid | ✅ |

### Bugs found

#### #13 `<a href>` instead of `<Link>` to a Next.js page

**Where:** `apps/web/src/app/auth/error/page.tsx`
**Symptom:** ESLint error
`@next/next/no-html-link-for-pages`.
**Fix:** Use `next/link`'s `<Link>`.

#### #14 `index = "index"` in StrEnum shadows `str.index()`

**Where:** `services/db/src/brokerapp_db/models.py:37`
**Symptom:** `mypy --strict`:
`Incompatible types in assignment (expression has type "AssetClass",
base class "str" defined the type as "Callable[[str, …], int]")`.
**Fix:** Added `# type: ignore[assignment]` with a comment explaining
the StrEnum quirk. Runtime semantics are correct.

#### #15 `cal.is_trading_minute(...)` returns Any, declared bool

**Where:** `services/ingest/src/ingest/calendars.py:47`
**Symptom:** `mypy: Returning Any from function declared to return
"bool"`.
**Fix:** Wrapped in `bool(...)`.

#### #16 Stale `# type: ignore[union-attr]` in yfinance adapter

**Where:** `services/ingest/src/ingest/sources/yfinance_source.py:96`
**Symptom:** `mypy: Unused "type: ignore" comment`.
**Fix:** Removed the suppression — the upstream typing has caught up.

#### #17 + #18 Polars schema dict mixed `Datetime(...)` instances with `Float64` class refs

**Where:**
- `services/ingest/src/ingest/sources/yfinance_source.py:_empty_frame`
- `services/ingest/src/ingest/sources/ccxt_source.py:_empty_frame`

**Symptom:** `mypy: Argument "schema" to "DataFrame" has incompatible
type "dict[str, object]"; expected …`.
**Fix:** Switched to a list of `(name, instance)` tuples and
instantiated `pl.Float64()` so every value has the same DataType
shape.

#### #19 Celery `@app.task` decorator is untyped → mypy strict bites

**Where:** `services/ingest/src/ingest/tasks.py`
**Symptom:** Cascade of `untyped-decorator` and `no-untyped-def`
errors on every Celery task because `Celery.task` returns `Any` and
forces every wrapped function to be untyped too.
**Fix:** File-level
`# mypy: disable-error-code="untyped-decorator,no-untyped-def"` with
the rationale documented inline. Other type-checks remain strict.

#### #20 brokerapp_db / brokerapp_ml missing `py.typed` marker

**Where:** `services/db/src/brokerapp_db/`,
`ml/src/brokerapp_ml/`
**Symptom:** Cascade of `Skipping analyzing "brokerapp_db": module is
installed, but missing library stubs or py.typed marker`.
**Fix:** Added empty `py.typed` files. PEP 561 says hatch picks them
up automatically from a package directory.

### Bonus side-effects

- **57 files prettier-reformatted** during the second pass — almost
  all docs / markdown / chart YAML that prettier wanted normalised.
  The runbooks now look identical to what CI would render.
- **`# type: ignore[no-untyped-call]`** on `redis_async.from_url()` —
  redis-py 5.x still ships no stubs for that surface; one-liner.
- **`return dict(claims)`** in `apps/api/src/api/auth.py:_verify_token`
  to drop the Any from `jwt.decode()`'s return.
- **mypy.overrides** extended with the full ML / Celery / structlog
  family, plus the explicit `brokerapp_ml.*` ignore (it's a lazy
  import in the risk endpoints; the API container doesn't ship it).

### Bottom line — pass 2

Together with the first pass: **20 bugs** found and fixed before any
of them could blow up CI or a deploy. The repo now passes every
static-analysis tool we wired into the pipeline (`ruff`,
`ruff format`, `mypy --strict`, `next lint`, `prettier`, `helm lint`,
`kubeconform`) end-to-end on a clean checkout.

What still needs the real cluster: Docker builds, Authentik OIDC
roundtrip, yfinance / ccxt live data, Darts training, Expo bundle —
all flagged at the bottom of [step 95](./95-deploy.md).
