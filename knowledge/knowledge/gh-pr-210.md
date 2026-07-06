---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#210
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/210
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620671+00:00'
updated: '2026-07-06T20:55:53.620671+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# chore(ci): sync advisors baseline post round-2 prod apply

## Summary
Post prod-apply sync: +3 owns_workout/owns_template/owns_workout_exercise (benign RLS-helper class, created by RC-2 helpers applied to prod today), −1 is_minor (EXECUTE revoked in P1-2 — advisors improvement). Without this the daily db-advisors gate would false-positive on its first armed run.

## Details
Post prod-apply sync: +3 owns_workout/owns_template/owns_workout_exercise (benign RLS-helper class, created by RC-2 helpers applied to prod today), −1 is_minor (EXECUTE revoked in P1-2 — advisors improvement). Without this the daily db-advisors gate would false-positive on its first armed run.

## Context
PR #210 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/210
