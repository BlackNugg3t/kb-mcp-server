---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#146
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/146
tags:
- security
- source:github
created: '2026-07-06T20:46:19.372423+00:00'
updated: '2026-07-06T20:46:19.372423+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# [GBA-16] Add CHECK constraints + validation for workout_sets reps/weight/rpe (no bounds today)

## Summary
Live DB workout_sets columns (weight, reps, rpe, rir, duration_seconds) are all nullable with no bounds. No validation exists at any layer. A tampered client can persist reps=-999999, weight=1e308, corrupting analytics and trainer dashboards. Fix: add DB CHECK constraints + server-side validation.

## Details
Live DB workout_sets columns (weight, reps, rpe, rir, duration_seconds) are all nullable with no bounds. No validation exists at any layer. A tampered client can persist reps=-999999, weight=1e308, corrupting analytics and trainer dashboards. Fix: add DB CHECK constraints + server-side validation.

## Context
Issue #146 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/146
