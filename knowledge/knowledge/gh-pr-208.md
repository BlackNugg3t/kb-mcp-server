---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#208
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/208
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738744+00:00'
updated: '2026-07-06T21:16:37.738745+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# fix(db-smoke): remove user_1rm/feedback ALTER that conflicts with 20260705100300

## Summary
Hotfix: main's db-smoke went red the moment PR #206 merged (run 28737186435, SQLSTATE 42704). My security migration `20260705120000` ALTERed `"Users manage own 1RM"`, but concurrently-merged `20260705100300` drops that policy earlier in the replay chain, so the ALTER errors. Removes the two now-redu

## Details
Hotfix: main's db-smoke went red the moment PR #206 merged (run 28737186435, SQLSTATE 42704). My security migration `20260705120000` ALTERed `"Users manage own 1RM"`, but concurrently-merged `20260705100300` drops that policy earlier in the replay chain, so the ALTER errors. Removes the two now-redundant P2 lines (100300 already owns user_1rm + feedback). Migration-only; db-smoke validates.

## Context
PR #208 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/208
