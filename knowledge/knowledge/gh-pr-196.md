---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#196
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/196
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.739615+00:00'
updated: '2026-07-06T21:16:37.739617+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# fix: top verified issues from app-wide audit (observability, reliability, dark-mode, write-queue, card isolation)

## Summary
An app-wide audit (Sentry + Supabase advisors + recurring bug-class scan + 3 code-review lenses + trackers), with every candidate adversarially re-verified against the current code/DB before fixing. 24 issues confirmed live; 8 candidates were knocked out as already-fixed or false-positives.

### Fix

## Details
An app-wide audit (Sentry + Supabase advisors + recurring bug-class scan + 3 code-review lenses + trackers), with every candidate adversarially re-verified against the current code/DB before fixing. 24 issues confirmed live; 8 candidates were knocked out as already-fixed or false-positives.

### Fixed
- **AuthProvider** dropped `error` on the profile fetch and called `setProfile(null)` on any failure — wiping trainer role / `gym_id` / every role-gated feature. Now captures to Sentry and preserves the warm cached profile.
- `getTemplates`, the template-sets insert, and the admin trainer-applications page no longer mask DB errors as empty/success.
- **Transient PostgREST "schema cache" error** is now retried once via `withSchemaCacheRetry()`.
- **Write-queue**: a terminally-failed op now halts the rest of its FIFO group.
- UTC `toISOString().slice(0,10)` wrong-day bug (×3) → `localDateKey()`.
- Dark mode: inline hex colors → themeable Tailwind classes.
- Error boundary around each workout card.

## Context
PR #196 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/196
