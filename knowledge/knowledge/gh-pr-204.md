---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#204
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/204
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738766+00:00'
updated: '2026-07-06T21:16:37.738767+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# test(db): baseline capture of the dashboard-era schema (db-smoke unblock)

## Summary
Draft PR to run db-smoke CI against the fresh-DB replay. Baseline migration 20260422000000 captures the dashboard-era schema (16 tables + 3 functions + RLS policies) that no tracked migration creates — reconstructed from live prod DDL minus later migration additions. Guarded throughout, no-op on pro

## Details
Draft PR to run db-smoke CI against the fresh-DB replay. Baseline migration 20260422000000 captures the dashboard-era schema (16 tables + 3 functions + RLS policies) that no tracked migration creates — reconstructed from live prod DDL minus later migration additions. Guarded throughout, no-op on prod.

Validation = the db-smoke workflow on this PR: full migration replay + plpgsql_check + pgTAP RLS suite (8 files, first-ever run).

## Context
PR #204 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/204
