---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#116
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/116
tags:
- bug
- source:github
created: '2026-07-06T20:46:19.372373+00:00'
updated: '2026-07-06T20:46:19.372373+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# Workouts saved with duration 0 ("HOTOVO 0 min")

## Summary
Completed workouts always display "HOTOVO 0 min" — handleFinish hardcodes duration_seconds: 0 at TrainingTab.tsx:1060, even though both startedAt and finishedAt are already computed.

## Details
Completed workouts always display "HOTOVO 0 min" — handleFinish hardcodes duration_seconds: 0 at TrainingTab.tsx:1060, even though both startedAt and finishedAt are already computed.

## Context
Issue #116 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/116
