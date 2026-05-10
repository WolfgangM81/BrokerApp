# ADR-0002: Monorepo with pnpm + uv workspaces

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

BrokerApp has TypeScript apps (`web`), Python apps (`api`, workers, ML), and
shared packages (generated API client, UI components). We need a layout that:

- Lets all of these be developed and tested together,
- Shares types between Python (Pydantic / OpenAPI) and TypeScript (generated
  client) without copy-paste,
- Makes atomic deploys possible (one commit changes API + web together),
- Plays well with a single GitLab CI pipeline.

## Decision

A single Git repository (`monorepo`) using:

- **`pnpm` workspaces** for TypeScript packages, declared in
  `pnpm-workspace.yaml`. Members: `apps/*`, `packages/*`.
- **`uv` workspaces** for Python packages, declared in root `pyproject.toml`
  under `[tool.uv.workspace]`. Members: `apps/api`, `services/*`, `ml`.

Top-level layout:

```
apps/         user-facing (web, api)
services/     background workers (ingest, forecast, notifier)
packages/     shared TS libraries
ml/           Python research, feature engineering, models
infra/        Helm, Dockerfiles, Grafana dashboards
docs/         ARCHITECTURE.md, ADRs, runbooks
```

Single GitLab CI pipeline; per-project jobs use path-based `rules:changes`
to only run when relevant files change.

## Consequences

**+** Atomic changes across API and web in one commit.
**+** Generated API client (`packages/api-client`) imported directly by `web`.
**+** One CI to rule them all; fewer auth/CI-config sprawl.
**−** Cluster-wide lockstep — must coordinate breaking changes carefully.
**−** Some tooling (IDE, language servers) needs explicit configuration to
       handle multi-language workspace.
