# ADR-0013: Mobile client — Expo (React Native) sharing the typed API client

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

We want a mobile experience without rebuilding the API surface for it.
The two viable React Native paths are:

- **Expo Router** — managed workflow, OTA updates, EAS Build, batteries
  included.
- **Bare React Native** — full native control, more work.

Phase 7's bar is "watchlists + alerts on the go", not native widgets.
We pick the lighter path.

## Decision

- **Expo SDK 52 with the App Router (`expo-router`)** lives at
  `apps/mobile/`.
- It is a `pnpm` workspace member; it imports the same
  `@brokerapp/api-client` package as the web app — neither client
  duplicates request code or types.
- **Auth is OIDC against Authentik** via `expo-auth-session` with PKCE.
  Tokens live in `expo-secure-store` (Keychain on iOS, Keystore on
  Android). A second Authentik application (`brokerapp-mobile`,
  public client) is required.
- **Push notifications via Expo's notification service** for now;
  Phase 7.x can swap to ntfy.sh-native if we want fully self-hosted
  push.
- **State management:** TanStack Query (same as web) — one
  `QueryClient` per app, the offline plugin is added later if needed.
- **Charting** is left for a Phase 7.x follow-up: TradingView
  Lightweight Charts is web-only; the candidates are
  `react-native-skia` (custom draw) or a simpler
  `react-native-svg-charts` fallback.

## Consequences

**+** Shared API client → no schema drift between web and mobile.
**+** Expo's managed runtime makes builds reproducible without a Mac
       in the loop (EAS Build handles the iOS side).
**−** Some native modules (e.g. WatchKit complications) require
       prebuild + custom config plugins, which we don't have yet.
       Acceptable for the alerts / read-only use case.
**−** Two Authentik applications (web + mobile) to keep in sync.
       Mitigated by documenting the second one in `apps/mobile/README.md`.
