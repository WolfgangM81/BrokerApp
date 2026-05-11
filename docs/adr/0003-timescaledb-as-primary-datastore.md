# ADR-0003: TimescaleDB as primary datastore

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

The product needs to store:

1. Large volumes of time-series bars (OHLCV) at 5-minute granularity for
   thousands of assets, with fast range and aggregation queries.
2. Relational application metadata: users, watchlists, forecasts, backtests,
   trades, paper portfolios.

Options considered:

- **Two databases** (e.g. InfluxDB for bars + Postgres for metadata).
  Strong on time-series, but operationally heavier and joining across them is
  awkward.
- **Postgres only**, no time-series extension. Fine for metadata, weaker on
  hypertable-style query patterns and continuous aggregates.
- **TimescaleDB** (Postgres extension): hypertables for time-series,
  continuous aggregates for rollups, regular tables for metadata, all in one
  engine, all queryable via SQL with first-class joins.

## Decision

Use **TimescaleDB** (Postgres 16 + Timescale extension) as the single primary
datastore. Bars live in a hypertable partitioned on `time`. Metadata lives in
ordinary tables in the same instance (separate logical schemas if it helps
clarity). Continuous aggregates roll up bars to 15m / 1h / 1d.

## Consequences

**+** One datastore to back up, monitor, secure.
**+** Joins between bars and metadata are trivial.
**+** Continuous aggregates handle most chart-aggregation needs in the DB.
**+** Self-hostable on the Longhorn StorageClass; no cloud lock-in.
**−** Operational know-how for hypertable maintenance (chunks, compression,
retention policies) is required.
**−** Not as fast as specialized columnar TSDBs at extreme scale — acceptable
for our scale (thousands of assets, intraday bars over years).
