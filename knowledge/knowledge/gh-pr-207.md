---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#207
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/207
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620697+00:00'
updated: '2026-07-06T20:55:53.620697+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# fix(db): CI-only migration-replay role drift (user_1rm orphan + feedback role)

## Summary
Fixes the db-smoke failure that just surfaced on main (run 28735356207) now that the TASK-01 baseline lets migrations replay from scratch for the first time. Both are migration-FILE-history gaps, not live prod issues (verified prod already has the safe state).

1. user_1rm: 20260603120000 tried to d

## Details
Fixes the db-smoke failure that just surfaced on main (run 28735356207) now that the TASK-01 baseline lets migrations replay from scratch for the first time. Both are migration-FILE-history gaps, not live prod issues (verified prod already has the safe state).

1. user_1rm: 20260603120000 tried to drop "Manage own 1RM" but the original policy is named "Users manage own 1RM" (20260424140000) - name mismatch made the DROP a no-op, leaving an orphaned TO-public ALL policy alongside the 4 new per-command authenticated ones.
2. feedback: baseline created "users can insert feedback" with no TO clause (defaults to public); no migration file ever tightened it. Not exploitable (WITH CHECK still requires auth.uid() = user_id) but breaks the TO-authenticated-only invariant.

Throwaway validation branch only - merging this closes db-smoke red on main.

## Context
PR #207 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/207
