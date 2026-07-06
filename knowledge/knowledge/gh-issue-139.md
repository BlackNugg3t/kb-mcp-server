---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#139
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/139
tags:
- security
- source:github
created: '2026-07-06T20:46:19.372385+00:00'
updated: '2026-07-06T20:46:19.372385+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# [GBA-09] savePlannedWorkout delete-then-insert opens a zero-exercise window with no transaction

## Summary
PostgREST gives no cross-statement transaction; between the delete and the insert the plan exists with zero exercises. If insert fails, the plan is left with ALL exercises deleted. Fix: move delete to AFTER new workout_exercises (+ sets) are fully inserted, or use a single Postgres RPC.

## Details
PostgREST gives no cross-statement transaction; between the delete and the insert the plan exists with zero exercises. If insert fails, the plan is left with ALL exercises deleted. Fix: move delete to AFTER new workout_exercises (+ sets) are fully inserted, or use a single Postgres RPC.

## Context
Issue #139 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/139
