---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#205
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/205
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620649+00:00'
updated: '2026-07-06T20:55:53.620649+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# Security/reliability root-cause fixes (RC-1, RC-3, RC-2)

## Summary
Root-cause fixes from the Sentry/audit fan-out plan. **Preview/validation branch — merge is go-live-gated (not this PR).** Opened primarily to run **db-smoke** (migrations + pgTAP + the new authz-invariant guard) against a fresh Postgres before any prod apply.

## What's in it (9 commits)
**RC-1 — s

## Details
Root-cause fixes from the Sentry/audit fan-out plan. **Preview/validation branch — merge is go-live-gated (not this PR).** Opened primarily to run **db-smoke** (migrations + pgTAP + the new authz-invariant guard) against a fresh Postgres before any prod apply.

## What's in it (9 commits)
**RC-1 — schema-cache boundary (biggest reliability+noise win)**
- Reads route through `supabase-fetch.ts` wrappers → `withSchemaCacheRetry` (2×/250ms exp); 7 fetchers migrated.
- Writes: `isTransientWriteError` retries the transient (Fixes GYMBOOST-M).
- Sentry noise pattern + new `unretried-supabase-read` guard class (108 reads baselined).
- Final review hardening: matchers tightened to the **exact PGRST002** sentence (bare "schema cache" collided with the *permanent* PGRST200).

**RC-3 — dependency advisories**
- Overrides for undici/vite/js-yaml/@opentelemetry-core (capped `<8` to stay on supported majors) + `@sentry/nextjs ^10.54`. `npm audit` clears all 4 GHSAs; build green.

**RC-2 — DB authz hardening (NOT applied to prod; owner-gated)**
- `workout_exercises_select` `TO public` → `TO authenticated`.
- `owns_workout`/`owns_template`/`owns_workout_exercise` SECDEF helpers replace inline-subquery RLS (the db10 recursion footgun). Owner-OR-trainer semantics preserved (independently re-verified against live prod).
- db-smoke `authz_invariants.sql`: blocks net-new `TO public` on RLS tables + anon-executable SECDEF; advisory recursion heuristic.

## Validation
tsc 0 · guard 0 · ~140 focused tests green · npm audit clean. db-smoke will validate the DB layer here.

## Known follow-ups (owner)
- Pre-existing `workout_id IS NULL` template-exercise structure read (not a regression; needs template-visibility decision).
- RC-4 Vercel Skew Protection toggle (GYMBOOST-A). Anon-sign-in advisor category. Deferred Sentry noise strings.

## Context
PR #205 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/205
