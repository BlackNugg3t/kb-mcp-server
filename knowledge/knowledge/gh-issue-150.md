---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#150
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/150
tags:
- bug
- source:github
created: '2026-07-06T20:46:19.372323+00:00'
updated: '2026-07-06T20:46:19.372326+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# [reliability] createClientPlan: non-transactional delete+insert can gut a client's assigned plan (GBA-09 sibling, trainer path)

## Summary
Sibling of GBA-09 (#139, fixed in 328490d). createClientPlan (src/services/trainer.ts, ~line 743) still replaces an existing assigned plan via a non-transactional delete+insert sequence on the ADMIN client: workout_exercises delete → workout update → insertPlanExercises. Any failure after the delete

## Details
Sibling of GBA-09 (#139, fixed in 328490d). createClientPlan (src/services/trainer.ts, ~line 743) still replaces an existing assigned plan via a non-transactional delete+insert sequence on the ADMIN client: workout_exercises delete → workout update → insertPlanExercises. Any failure after the delete (constraint, network, cold-start timeout) leaves the client's assigned plan gutted — exercises gone or exercises without sets. Fix pattern (proven by GBA-09): one plpgsql RPC = one transaction.

## Context
Issue #150 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/150
