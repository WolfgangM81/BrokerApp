# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

We are starting a multi-phase project (BrokerApp) with a non-trivial stack and
several decisions whose rationale would otherwise be lost over time. We want a
lightweight way to record those decisions for future contributors (humans and
AI agents) without resorting to a heavyweight RFC process.

## Decision

We will keep Architecture Decision Records (ADRs) in `docs/adr/`, one Markdown
file per decision, numbered sequentially: `NNNN-kebab-case-title.md`.

Each ADR has the following sections:
- **Status** — Proposed / Accepted / Deprecated / Superseded by ADR-NNNN
- **Date** — ISO date
- **Context** — what made this decision necessary
- **Decision** — what we decided
- **Consequences** — what we're now committed to (good and bad)

ADRs are immutable once Accepted. To revise, write a new ADR that supersedes.

## Consequences

**+** Decisions are discoverable and revisitable.
**+** Future agents/contributors can read context without re-deriving it.
**−** Small overhead per significant decision; we accept it.
