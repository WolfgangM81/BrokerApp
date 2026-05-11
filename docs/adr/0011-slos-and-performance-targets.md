# ADR-0011: SLOs and performance targets

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

Without explicit targets we have no way to say "this is fast enough" or
"this needs optimization". We also have no signal for Grafana alerts.

The cluster is CPU-only (3× Ryzen 5 PRO 3400GE) — targets must respect
the hardware, not aspirational SaaS numbers.

## Decision

### API (non-ML endpoints)

| Metric           | Target   | Window |
| ---------------- | -------- | ------ |
| p50 latency      | < 100 ms | 5 min  |
| p95 latency      | < 300 ms | 5 min  |
| p99 latency      | < 1 s    | 5 min  |
| Error rate (5xx) | < 0.5 %  | 5 min  |

### ML endpoints

| Metric                                               | Target            |
| ---------------------------------------------------- | ----------------- |
| Forecast inference (single asset, single horizon)    | < 5 s p95         |
| Backtest (5-year window, daily bars, one model)      | < 5 min p95       |
| Walk-forward backtest (5-year window, all baselines) | < 30 min p95      |
| Model retrain (all global TFT, full universe)        | < 8 h (overnight) |

### Frontend (web)

| Metric                           | Target               |
| -------------------------------- | -------------------- |
| LCP (Largest Contentful Paint)   | < 2.5 s on cold load |
| TTFB                             | < 600 ms             |
| Interaction → response on action | < 250 ms             |

### Availability

Homelab; no formal SLO. **Best-effort with alerting**: any continuous
downtime > 5 min pages via ntfy.sh. Monthly availability is not measured
formally; if it dips below ~99 % we investigate.

### Pipeline freshness

| Metric                                               | Target                      |
| ---------------------------------------------------- | --------------------------- |
| Bar ingest lag (last bar in DB vs source) — intraday | < 20 min                    |
| Bar ingest lag — EOD                                 | < 60 min after market close |
| Nightly retrain completion                           | before 06:00 Europe/Berlin  |

## Consequences

**+** Concrete numbers — Grafana alerts can be wired in Phase 4.
**+** Honest targets — CPU-only hardware, no false promises.
**−** We may miss them initially. SLOs are a conversation starter, not a
contract; we revise as data comes in.

## Monitoring

- All targets are emitted as Prometheus metrics from `apps/api`,
  `services/ingest`, and `services/forecast`.
- Grafana dashboards live in `infra/grafana-dashboards/`. Concrete
  dashboards land in Phase 4; the metric names are committed now so the
  code points at the eventual targets.
