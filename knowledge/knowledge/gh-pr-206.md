---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#206
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/206
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738752+00:00'
updated: '2026-07-06T21:16:37.738752+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# fix(security): 4 P0 RLS holes + 2 GDPR data-loss + unblock main db-smoke (audit 2026-07-05)

## Summary
fix(security): close 4 P0 cross-tenant RLS holes + 2 GDPR data-loss bugs (audit 2026-07-05)

Rebased onto current main (which already merged the db-smoke baseline PR #204 and security root-causes PR #205). Reconciled with RC-2: main's 20260705100000 narrowed workout_exercises_select's ROLE to authen

## Details
fix(security): close 4 P0 cross-tenant RLS holes + 2 GDPR data-loss bugs (audit 2026-07-05)

Rebased onto current main (which already merged the db-smoke baseline PR #204 and security root-causes PR #205). Reconciled with RC-2: main's 20260705100000 narrowed workout_exercises_select's ROLE to authenticated (closing the anon leak) but left the leaky workout_id-IS-NULL disjunct — this finishes that (owner-only template children). Also fixes the two TO-public policies (user_1rm, feedback) that RC-2's authz-invariant guard currently flags red on main.

All P0s share one shape: WITH CHECK (or a missing one) pins only the actor's own id, leaving the counterparty column free — reachable via direct PostgREST. Legit writes go through SECURITY DEFINER RPCs.

- P0-1 trainer_clients: any user could self-attach as a victim's coach
- P0-2 coach_sessions/coach_client_notes: plant rows in a stranger's account
- P0-3 workout_exercises: drop the leaky workout_id-IS-NULL disjunct
- P0-4 posts: trigger pins posts.hidden for non-postgres
- P2: user_1rm + feedback → TO authenticated

## Context
PR #206 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/206
