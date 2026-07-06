---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#200
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/200
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.739646+00:00'
updated: '2026-07-06T21:16:37.739646+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# refactor(training): remove dead in-tab finish/summary path (Task 1.3)

## Summary
Full-screen LiveWorkoutScreen now owns the live finish flow (it calls session.checkFinish()/finish() with its own empty/unchecked/bounds dialogs and summary). In-tab live cards became a "Continue →" entry in DayPlanList, so cardPrimaryAction never fires for a live workout — the old in-tab finish cha

## Details
Full-screen LiveWorkoutScreen now owns the live finish flow (it calls session.checkFinish()/finish() with its own empty/unchecked/bounds dialogs and summary). In-tab live cards became a "Continue →" entry in DayPlanList, so cardPrimaryAction never fires for a live workout — the old in-tab finish chain was unreachable.

Removed (435 lines): handleFinish, attemptFinish, the live branch of cardPrimaryAction, the 3 finish ConfirmDialogs, the in-tab summary screen JSX, and all state/computed values only it used.

## Context
PR #200 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/200
