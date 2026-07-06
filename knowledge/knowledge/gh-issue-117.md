---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#117
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/117
tags:
- bug
- source:github
created: '2026-07-06T20:46:19.372348+00:00'
updated: '2026-07-06T20:46:19.372349+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# Set can be marked complete with empty fields (no validation)

## Summary
The "Complete set" tick fires with no validation — an empty set (no reps/weight/etc.) can be marked done. src/components/training/SetRow.tsx:67-78 — the complete button's onClick calls onToggleComplete?.(set.localId) unconditionally.

## Details
The "Complete set" tick fires with no validation — an empty set (no reps/weight/etc.) can be marked done. src/components/training/SetRow.tsx:67-78 — the complete button's onClick calls onToggleComplete?.(set.localId) unconditionally.

## Context
Issue #117 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/117
