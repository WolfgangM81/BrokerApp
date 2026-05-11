# ADR-0004: Authentik (OIDC) for authentication

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

BrokerApp is multi-user (small group, household-scale) and lives behind a
homelab ZeroTier network. Authentik is already deployed in the cluster and
provides OIDC, SAML, LDAP, and group-based RBAC.

Building our own auth (passwords, sessions, password reset, 2FA, …) would be
a significant time sink and a needless reinvention.

## Decision

- **Identity provider:** Authentik (existing).
- **Web → API auth:** Auth.js v5 in Next.js with Authentik as an OIDC
  provider. Web stores a session cookie; API receives the access token in
  `Authorization: Bearer …`.
- **API verification:** stateless JWT verification against Authentik's JWKS
  endpoint. No DB session lookup on the request path.
- **Local user record:** a `users` row keyed by Authentik `sub` (subject)
  claim, holding app-specific preferences (watchlists, base currency, etc.).
- **Authorization:** Authentik group memberships flow through as JWT claims
  and gate API endpoints (`admin`, `paper-trader`, `read-only`, …).

## Consequences

**+** Zero password code in our repo. SSO with whatever else lives in the
homelab.
**+** Stateless API; horizontally scalable.
**+** Future mobile clients use the same OIDC flow.
**−** Hard dependency on Authentik availability. Mitigated by it being an
existing, monitored service in the cluster.
**−** Local `users` table can drift from Authentik over time; periodic
reconciliation job lives in `services/notifier` (or its own tiny
cron).
