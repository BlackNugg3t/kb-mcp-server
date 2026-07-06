---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#206
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/206
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620690+00:00'
updated: '2026-07-06T20:55:53.620690+00:00'
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

All P0s share one shape: WITH CHECK (or a missing one) pins only the actor's own id, leaving the counterparty column free — reachable via direct PostgREST. Legit writes go through SECURITY DEFINER RPCs (run as postgres, bypass these guards), so only the abuse paths close.

20260705120000_security_p0_rls_hardening:
- P0-1 trainer_clients: any user could self-attach as a victim's coach and read their full training data. INSERT pending-only + client<>trainer; BEFORE-UPDATE trigger blocks id-repoint + direct status=accepted escalation.
- P0-2 coach_sessions/coach_client_notes: plant rows in a stranger's account. WITH CHECK now requires coach_target_is_mine() (accepted client or own shadow) — mirrors app assertCoachTarget.
- P0-3 workout_exercises: drop the leaky workout_id-IS-NULL disjunct (RC-2 did the role half). Template children now owner-only.
- P0-4 posts: trigger pins posts.hidden for non-postgres (report_content DEFINER).
- P2: user_1rm "Users manage own 1RM" + feedback "users can insert feedback" -> TO authenticated (unblocks main's authz-invariant guard).

20260705120100_gdpr_deletion_retention:
- user_goals.exercise_id -> ON DELETE CASCADE + clearData() deletes user_goals (fixes the FK-strand that stuck accounts mid-clear).
- Account-deletion ledger wipe: snapshot trainer/client name + ON DELETE SET NULL on the coach ledger/sessions/notes (competition_results pattern; GDPR Art.17(3) retention). Backfill + snapshot triggers.

Tests: security_p0_regression.sql (8 negative-first); workout_templates.sql now asserts trainer + anon both is_empty on template children; sessions/notes fixture seeds the accepted link the tightened policy requires; profile.test.ts clearData order. Local: tsc 0, profile + coach-crm vitest green.

Not applied to prod — CI-validated here, prod apply on owner go.

## Context
PR #206 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/206
