-- Initial DB setup for local development.
-- Production setup is driven by Alembic migrations (see apps/api/migrations/).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Schemas
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS mlflow;

COMMENT ON SCHEMA app IS 'Application metadata: users, watchlists, forecasts, trades.';
COMMENT ON SCHEMA market IS 'Market data: assets, bars (hypertables), aggregates.';
COMMENT ON SCHEMA mlflow IS 'MLflow tracking server backend.';
