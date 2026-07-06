---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#135
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/135
tags:
- bug
- security
- source:github
created: '2026-07-06T20:46:19.372402+00:00'
updated: '2026-07-06T20:46:19.372402+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# [GBA-05] BootstrapProvider: stale ghost-user bootstrap lands in new user's context (no cancel guard)

## Summary
On account switch without a full page reload, an in-flight cold-path bootstrapCoreData() for user A resolves AFTER the effect re-runs for user B and writes A's workouts/plans into B's BootstrapContext. Fix: add per-run cancellation token and guard every setState behind it.

## Details
On account switch without a full page reload, an in-flight cold-path bootstrapCoreData() for user A resolves AFTER the effect re-runs for user B and writes A's workouts/plans into B's BootstrapContext. Fix: add per-run cancellation token and guard every setState behind it.

## Context
Issue #135 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/135
