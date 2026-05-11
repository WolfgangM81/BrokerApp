# Roadmap — Phase 9 and beyond

The repo as it stands today (Phase 8.7) is **cluster-deploy-ready**.
This document plans the work that comes after: real ML / ops
investments that will only pay off once production telemetry is
available. Everything below has a **trigger condition** — start the
phase when the trigger fires, not when it sounds fun.

Use this doc as the source of truth when planning the next sprint.
The ADRs in [`docs/adr/`](adr/) record committed decisions; this doc
records *upcoming* ones.

---

## Decision rules

1. **No phase starts before its trigger.** "Cool tech" is not a
   trigger. Production pain is.
2. **One phase at a time.** No interleaving. Finish, ship, observe,
   then plan the next.
3. **Every phase has an acceptance check** that's verifiable by a
   test, metric, or kubectl one-liner. If you can't write the check,
   the phase isn't ready to start.
4. **Every phase is its own commit on its own branch**, just like
   Phases 0–8.7.

---

## Phase 9 — Observability + Performance Foundations

Goal: be able to **see** what's slow before we **fix** what's slow.
After Phase 8.7 the system has Prometheus + Loki but no distributed
tracing and no lazy/columnar fast-paths.

| Sub | Title | Trigger | Effort | ADR-needs |
|-----|-------|---------|--------|-----------|
| 9.1 | OpenTelemetry traces | First "where is the latency?" question we can't answer from logs alone | M | new ADR-0015 |
| 9.2 | Polars LazyFrame refactor | Backtest run > 60 s for a single asset on daily bars | S | extend ADR-0007 |
| 9.3 | DuckDB read-layer | Walk-forward backtest with > 5 years history takes > 5 min | M | new ADR-0016 |
| 9.4 | Ray for distributed training | TFT/N-HiTS retrain on full universe > 4 h on one node | L | extend ADR-0005 |

### 9.1 OpenTelemetry traces

**Why:** A single user action (e.g. "add SPY to watchlist") fans out
across Web → API → Celery dispatch → Worker → DB → another API call.
Right now we correlate via `request_id` in structured logs. Tracing
lets us see the *shape* of that fan-out and the time each hop took.

**What gets built:**
- `opentelemetry-api` + `opentelemetry-sdk` + the `auto-instrumentation`
  packages for FastAPI, SQLAlchemy, Celery, httpx.
- OTel Collector deployment (`infra/helm/observability/otel-collector/`)
  with a Loki exporter for log-trace correlation and a Tempo/Jaeger
  exporter for the actual spans (Tempo because it's in the Grafana
  family and we already run Loki).
- `tempo`-Helm-Install in step 50 (extend `50-monitoring.md`).
- Existing structlog gains `trace_id` and `span_id` via
  `opentelemetry.trace.get_current_span()`.

**Acceptance:**
- Grafana → Explore → Tempo can render a flame-chart for a single
  watchlist-add round-trip.
- A LogQL query `{trace_id="..."}` finds the log lines from all
  three services for that trace.

**Effort:** Medium. ~2 days of focused work.

### 9.2 Polars LazyFrame refactor

**Why:** ADR-0007 made Polars our primary DataFrame library. The
implementation in `ml/src/brokerapp_ml/features/indicators.py` is
**eager** — every intermediate frame is materialised. LazyFrame
defers the chain and the planner removes redundant work.

**What gets built:**
- Convert `build_features` to return a `LazyFrame`; callers do
  `.collect()` at the end.
- Backtest engine streams windows through `lazy.slice(...)` instead
  of pre-materialising every fold.
- A small "perf" test that locks in the speed: ≥ 2× faster on a
  5-year SPY backtest than the eager version.

**Acceptance:**
- `pytest -k perf_features` passes the 2× target on the SPY fixture.
- All existing tests still green.
- `mypy --strict` still clean (LazyFrame is fully typed in Polars 1.x).

**Effort:** Small. ~half a day; mostly typing + benchmark.

### 9.3 DuckDB read-layer for backtests

**Why:** Backtests read **a lot** of historical bars but never write
them. Reading from a row-store hypertable (Postgres) is wasteful for
that pattern. DuckDB on the same data is 10–50× faster for analytical
scans.

**What gets built:**
- Nightly CronJob exports `market.bars_1d` to a partitioned Parquet
  tree in MinIO (`s3://mlflow-data/bars/year=YYYY/asset=…/`).
- `brokerapp_ml/io/duckdb_loader.py` opens DuckDB with the
  `httpfs` extension and `read_parquet(...)` directly from MinIO.
- Backtest engine grows a `source` parameter that picks
  Postgres-read (live, today's data) vs. DuckDB-read (historical,
  fixed snapshot).
- Cache invalidation: nightly export deletes yesterday's "live tail"
  rows from Parquet first, then writes them back. Atomicity via MinIO
  multipart upload + atomic-rename pattern.

**Acceptance:**
- Walk-forward backtest on SPY over 5 years: < 30 s wall-clock
  (today: ~5 min projected).
- A `pytest -k duckdb_consistency` test asserts the same bar values
  via Postgres vs DuckDB read on the same window.

**Effort:** Medium. ~2 days including CronJob + test.

### 9.4 Ray for distributed training

**Why:** ADR-0005 promised CPU-only ML on a 3-node cluster via global
TFT trained once across all assets. The implementation currently runs
on a single worker pod. With ~600 assets and a TFT, that's hours.
Ray Train splits the work across all three nodes.

**What gets built:**
- Helm sub-chart `infra/helm/ray/` (use the official KubeRay
  operator chart).
- `ml/src/brokerapp_ml/train/ray_runner.py` wraps the existing
  `Forecaster.fit()` in a `ray.train.Trainer`.
- `forecast.tasks.run_universe` triggers a Ray Job instead of
  Celery-fanning per asset.
- MLflow logging stays at the head node so the registry doesn't
  fragment.

**Acceptance:**
- Full-universe TFT retrain finishes < 2 h on the 3-node cluster
  (today: projected > 6 h on one node).
- Ray dashboard at `ray.brokerapp.orbiter` (cluster-internal).
- Failure of any worker doesn't take the run down (Ray's
  fault-tolerance kicks in).

**Effort:** Large. ~3-5 days, mostly because Ray + KubeRay has its
own learning curve and we'll discover scheduling quirks.

---

## Phase 10 — Intelligence

Goal: better signals, not just more data.

| Sub | Title | Trigger | Effort |
|-----|-------|---------|--------|
| 10.1 | FinBERT-based sentiment | Need actual sentiment-grade vs rule-based stub (ADR-0012) | S |
| 10.2 | Self-hosted LLM (Ollama + Mistral 7B) | Want auto-generated daily digest / news summaries | M |
| 10.3 | Argo Workflows for ML pipelines | Celery Beat schedules become tangled (>10 chained tasks) | L |

### 10.1 FinBERT sentiment

**Why:** ADR-0012 ships a `RuleBasedSentimentScorer` stub. FinBERT
gives F1 ≈ 0.85 on financial headlines vs. ~0.55 for our lexicon.
The full pipeline (NewsAPI / RSS → tokenizer → FinBERT → daily-mean
aggregator → feature join) is already exercised by the stub; only
the scorer itself swaps.

**What gets built:**
- Add `transformers` + `torch` (CPU-build) to `ml/pyproject.toml`.
- New `FinBERTSentimentScorer` class implementing the existing ABC.
- News-source ingest task (separate Celery worker pool — sentiment is
  bursty, separate queue from forecast).

**Acceptance:** Sentiment feature has non-trivial variance and lifts
backtest Sharpe by ≥ 0.05 on SPY (or it gets reverted — null result
is a valid result).

**Effort:** Small. ~1 day for the model swap, longer if news source
needs auth flows.

### 10.2 Self-hosted LLM

**Why:** "Read me a 3-bullet digest of yesterday's market relevant to
my watchlist." Tiny LLMs (Mistral 7B-Q4, Llama 3 8B) running on CPU
in the cluster do this acceptably — first token ~5 s, full response
~30 s. Acceptable for a once-a-day batch job.

**What gets built:**
- Helm sub-chart `infra/helm/ollama/` running on one m75q node.
- `services/notifier` extended with a `daily_digest` task that:
  1. Pulls yesterday's bars + top-5 forecast deltas for the user's
     watchlist.
  2. Builds a prompt + ships to Ollama.
  3. Sends the result via ntfy.sh with subject "BrokerApp daily".
- ADR-0017 on the prompt/model choice + cost-of-ownership.

**Acceptance:** Digest arrives in your phone every morning between
07:00–08:00 local time with a non-template body. ROUGE-L > 0.3
against a hand-written ground-truth on a 10-day sample.

**Effort:** Medium. ~3 days including prompt-engineering iteration.

### 10.3 Argo Workflows for ML pipelines

**Why:** Currently the dependency train (ingest → feature → train →
backtest → register → notify) lives in Celery Beat schedules + task
chaining. When that grows past ~10 dependent tasks, debugging
becomes painful. Argo Workflows is the right tool when it does.

**Don't start this until** Celery-Beat tangles up. As of Phase 8.7
it's fine.

**Effort:** Large. ~4-5 days including operator + first three
workflows.

---

## Phase 11 — Scale-out polish (only-if-needed)

Don't even plan these in detail until a metric demands it.

| Sub | Trigger | What |
|-----|---------|------|
| 11.1 PgBouncer | API replicas ≥ 5 *and* DB connection saturation | Transaction-pool in front of TimescaleDB |
| 11.2 CAGGs of CAGGs | We want monthly bars and don't want to scan daily | Hierarchical materialised view |
| 11.3 Cold storage | MinIO `bars/` exceeds 200 GB | Per-year compressed Parquet to a NAS, hot tier stays in MinIO |
| 11.4 HPA defaults flipped to true | First time the API hits 80% CPU on more than one replica | `helm upgrade --set api.autoscaling.enabled=true` |
| 11.5 Read-replica TimescaleDB | DB CPU > 60% sustained | Streaming replica + read routing in `brokerapp_db.queries` |

---

## Phase 12 — Decision-tool polish

Visible UX improvements that move the product from "data plumbing"
to "tool I actually use every morning".

| Sub | What | Trigger |
|-----|------|---------|
| 12.1 | Forecast confidence-band visualisation on the asset chart | After Phase 5 ships real Darts forecasts |
| 12.2 | Lot-tracking FIFO PnL for paper-portfolios (close out Phase 6) | First "this PnL number is wrong" complaint from yourself |
| 12.3 | Trade-journal UI in `apps/web` | Phase 4 ships the API; UI catch-up |
| 12.4 | Native candlestick charts in mobile (react-native-skia) | Phase 7 mobile sees real use |
| 12.5 | Survivorship-bias-aware backtests | When backtest results consistently > paper-trading results |
| 12.6 | Model-comparison leaderboard in UI | After ≥ 3 models have trained for ≥ 2 weeks |

---

## When to write each ADR

| ADR # | When to write |
|-------|---------------|
| 0015 — Distributed tracing with OpenTelemetry + Tempo | Start of Phase 9.1 |
| 0016 — DuckDB-on-Parquet for analytics reads | Start of Phase 9.3 |
| 0017 — Self-hosted Mistral 7B for daily digest | Start of Phase 10.2 |
| 0018 — Argo Workflows for ML pipelines | Start of Phase 10.3 |
| 0019 — Lot-tracking semantics for paper-portfolios | Start of Phase 12.2 |

---

## What's deliberately not in this roadmap

These come up in tech-stack reviews; the answer is "no" until something
listed below changes:

- **Microservices** — split the current "monolith + 2 workers" only if
  any service crosses 50 k LOC.
- **Event-Sourcing for trades** — only if regulatory audit demands it.
- **GraphQL** — OpenAPI is the contract (ADR-0008); REST + typed
  clients is sufficient for the foreseeable surface.
- **gRPC between services** — REST + Celery is fine until p95 inter-
  service latency exceeds 50 ms (currently single-digit ms intra-pod).
- **Multi-cloud / multi-region** — homelab; out of scope.

---

## Process for adopting this roadmap

1. When a trigger fires (or you have a quiet evening), pick the
   highest-priority unblocked phase.
2. Write its ADR first (decision before code).
3. Branch `claude/phase-<N>-<slug>`, one commit per sub-phase, push.
4. Open MR to main. CI runs the new + existing tests; smoke-test
   docs in `docs/runbooks/95-deploy.md` get extended where needed.
5. Update this doc — strike through the completed sub, add what was
   actually learned (effort estimate, surprises, follow-ups).

This roadmap is a **living document**: updates are commits like any
other. The version of truth is what's on `main` at any given moment.
