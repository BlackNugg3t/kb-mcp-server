---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#207
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/207
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738759+00:00'
updated: '2026-07-06T21:16:37.738759+00:00'
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
Fixes the db-smoke failure that just surfaced on main (run 28735356207) now that the TASK-01 baseline lets migrations replay from scratch for the first time. Both are migration-FILE-history gaps, not live prod issues.

1. user_1rm: 20260603120000 tried to drop "Manage own 1RM" but the original polic

## Details
Fixes the db-smoke failure that just surfaced on main (run 28735356207) now that the TASK-01 baseline lets migrations replay from scratch for the first time. Both are migration-FILE-history gaps, not live prod issues.

1. user_1rm: 20260603120000 tried to drop "Manage own 1RM" but the original policy is named "Users manage own 1RM" - name mismatch made the DROP a no-op, leaving an orphaned TO-public ALL policy.
2. feedback: baseline created "users can insert feedback" with no TO clause (defaults to public); no migration file ever tightened it.

## Context
PR #207 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/207
