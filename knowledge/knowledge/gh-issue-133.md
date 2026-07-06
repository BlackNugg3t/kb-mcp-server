---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#133
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/133
tags:
- security
- source:github
created: '2026-07-06T20:46:19.372408+00:00'
updated: '2026-07-06T20:46:19.372409+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# [GBA-03] Auth-lifecycle SIGNED_OUT silently destroys the entire offline write-queue (no drain, no warning)

## Summary
write-queue.ts uses NON-user-scoped key gymboost_wq. clearAllUserStorage() deletes every gymboost_* localStorage key. On SIGNED_OUT, pending offline workouts are destroyed with no banner and no user interaction. Fix: drain-before-purge + identity-scope the queue.

## Details
write-queue.ts uses NON-user-scoped key gymboost_wq. clearAllUserStorage() deletes every gymboost_* localStorage key. On SIGNED_OUT, pending offline workouts are destroyed with no banner and no user interaction. Fix: drain-before-purge + identity-scope the queue.

## Context
Issue #133 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/133
