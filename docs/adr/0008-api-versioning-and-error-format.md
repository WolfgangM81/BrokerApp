# ADR-0008: API versioning via path prefix; RFC 7807 errors with extensions

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

We need a long-lived contract for the API:

- A versioning scheme that lets us evolve the API without breaking existing
  clients (web, future mobile, possible CLI).
- A consistent error response shape that clients can rely on.

## Decision

### Versioning

- **Path prefix `/v1/...`.** Every domain endpoint lives under `/v1`. The
  unversioned endpoints `/healthz`, `/readyz`, `/metrics`, `/openapi.json`
  remain at the root for operational use.
- New major versions get a new prefix (`/v2/...`); they may coexist with
  `/v1/...` during a deprecation window.
- Minor / patch changes (additive only) stay in the current major.

### Error format

- **RFC 7807 Problem Details for HTTP APIs** as the base shape, with a
  small set of standard extension fields:
  ```json
  {
    "type": "https://brokerapp.orbiter/problems/asset-not-found",
    "title": "Asset not found",
    "status": 404,
    "detail": "No asset matches symbol 'XYZ'.",
    "instance": "/v1/assets/XYZ",
    "code": "asset.not_found",
    "request_id": "01J...",
    "errors": [{ "field": "symbol", "message": "must be uppercase" }]
  }
  ```
- `code` is a stable machine identifier (`asset.not_found`, `validation.failed`,
  `auth.invalid_token`), namespaced by domain.
- `errors[]` carries field-level validation problems for 422 responses.
- `request_id` carries the correlation id from logs.

## Consequences

**+** Industry-standard error format → clients can adopt off-the-shelf handlers.
**+** Path-based versioning is the most cache-, log-, and reverse-proxy-friendly
approach.
**−** Multiple major versions in parallel is some maintenance overhead — we
accept it when we get there.
**−** `code` field is ours to govern; we keep them in `apps/api/src/api/errors.py`
to avoid sprawl.
