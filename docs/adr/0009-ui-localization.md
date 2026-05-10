# ADR-0009: UI localization — German default, English fallback (next-intl)

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

The primary user writes in German; the UI should not feel like a foreign
tool. At the same time, third-party documentation, libraries, and the
codebase itself remain in English. We also want a clean fallback if
translations lag behind.

## Decision

- **`next-intl` for i18n** in the Next.js app.
- **German (`de`) is the default locale.** English (`en`) is the fallback
  for missing keys.
- **No URL prefix for the default locale** (`/dashboard` is German;
  `/en/dashboard` is English).
- **Date / number / currency formatting** via the native `Intl` API,
  driven by the active locale + the user's chosen base currency.
- Translation keys are namespaced by feature: `assets.list.title`,
  `watchlists.empty.cta`, etc. JSON message catalogs in
  `apps/web/messages/{de,en}.json`.
- Component code uses keys, never literal strings (`t('assets.list.title')`).

## Consequences

**+** UI feels native to the user; technical artifacts stay English.
**+** Easy to add Italian or French later (homelab is multi-user; family
       members may not all speak the same).
**−** Up-front discipline cost — devs must add keys, not strings.
**−** A missing-translation runtime check (or CI lint) is needed to keep
       `de` and `en` in sync; we add it in Phase 2 when the web app grows.
