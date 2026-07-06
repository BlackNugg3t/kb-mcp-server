---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#145
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/145
tags:
- security
- source:github
created: '2026-07-06T20:46:19.372417+00:00'
updated: '2026-07-06T20:46:19.372417+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# [GBA-15] Capture workout RLS policies + immutability trigger into migrations (schema drift)

## Summary
No migration file defines the workouts RLS policies or protect_workout_immutable_fields trigger. They exist live but were created out-of-band. A clean rebuild from migrations would come up WITHOUT workout RLS policies. Fix: capture live definitions into an idempotent migration.

## Details
No migration file defines the workouts RLS policies or protect_workout_immutable_fields trigger. They exist live but were created out-of-band. A clean rebuild from migrations would come up WITHOUT workout RLS policies. Fix: capture live definitions into an idempotent migration.

## Context
Issue #145 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/145
