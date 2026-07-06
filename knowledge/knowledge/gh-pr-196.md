---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#196
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/196
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620707+00:00'
updated: '2026-07-06T20:55:53.620707+00:00'
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
An app-wide audit (Sentry + Supabase advisors + recurring bug-class scan + 3 code-review lenses + trackers), with every candidate adversarially re-verified against the current code/DB before fixing. 24 issues confirmed live; 8 candidates were knocked out as already-fixed or false-positives. This PR 

## Details
An app-wide audit (Sentry + Supabase advisors + recurring bug-class scan + 3 code-review lenses + trackers), with every candidate adversarially re-verified against the current code/DB before fixing. 24 issues confirmed live; 8 candidates were knocked out as already-fixed or false-positives. This PR fixes the code-side issues; DB-permission hardening is staged but not applied.

## Fixed (code → this branch's Vercel preview)

### Observability / silent-empty (highest-value class)
- **AuthProvider** dropped `error` on the profile fetch and called `setProfile(null)` on any failure — wiping trainer role / `gym_id` / every role-gated feature for the whole session, and skipping the cache write. Now captures to Sentry (`op:auth_profile_fetch`) and **preserves the warm cached profile**.
- `getTemplates`, the template-sets insert, and the admin trainer-applications page no longer mask DB errors as empty/success.

### Reliability
- **Transient PostgREST "schema cache" error** is now retried once via a new `withSchemaCacheRetry()` at the 3 measurement/staff query sites.
- **Write-queue**: a terminally-failed op now **halts the rest of its FIFO group**.

### Correctness / dates
- UTC `toISOString().slice(0,10)` wrong-day bug (×3) → `localDateKey()`.

### UI / resilience
- **TrainingTab** detail-fetch effect had no dependency array (ran on every render) plus a retry storm on failure — both fixed.
- **Error boundary** around each workout card.
- **Dark mode**: inline hex colors → themeable Tailwind classes.

### Recurrence guard (fix-the-class)
- Lint ratchet baseline tightened **37 → 36**.

## Context
PR #196 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/196
