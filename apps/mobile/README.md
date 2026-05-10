# BrokerApp Mobile (Expo)

Phase-7 scaffold. Reuses `@brokerapp/api-client` so the same typed
client powers both the web (Next.js) and the mobile (Expo) experience.
Auth is OIDC against Authentik via `expo-auth-session` with PKCE.

## Status

What works in this scaffold:

- OIDC login flow (Authentik) using `expo-auth-session`, tokens stored
  in `expo-secure-store`.
- TanStack Query with the shared `ApiClient`.
- Two screens: home (list watchlists) and `/watchlists/[id]` (members).
- Push-notification scaffolding (`registerForPushNotifications` —
  request permission, get an Expo push token).

What's deliberately deferred:

- Native charting (TradingView's web library doesn't run in RN; we'll
  evaluate `react-native-skia` candlesticks in a follow-up).
- Watchlist write operations + asset search.
- Forecasts / paper-portfolio screens.

## Running

```bash
pnpm --filter @brokerapp/mobile install
cd apps/mobile
pnpm start
```

`expo-auth-session` requires a real device or emulator (it uses the
system browser); the redirect URI is `brokerapp://auth/callback` and
must be registered on the Authentik application alongside the web one.

## Authentik configuration

Create a second OIDC application in Authentik:

- Slug: `brokerapp-mobile`
- Redirect URIs: `brokerapp://auth/callback`
- Confidential = no (public client; PKCE is mandatory)
