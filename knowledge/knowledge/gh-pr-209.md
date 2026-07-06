---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#209
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/209
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620678+00:00'
updated: '2026-07-06T20:55:53.620678+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# fix(db): hardening round 2 — prevention rails + P1/P2 + race fixes (audit 2026-07-05)

## Summary
## DB hardening round 2 (audit 2026-07-05 follow-through)

Round 1 (4 P0 RLS holes + 2 GDPR data-loss) shipped in #206/#208 and is live on prod. This PR is the remaining owner-approved audit backlog — two prevention rails + P1 fixes + P2 batch + race fixes. All SQL verified against LIVE prod state (

## Details
## DB hardening round 2 (audit 2026-07-05 follow-through)

Round 1 (4 P0 RLS holes + 2 GDPR data-loss) shipped in #206/#208 and is live on prod. This PR is the remaining owner-approved audit backlog — two prevention rails + P1 fixes + P2 batch + race fixes. All SQL verified against LIVE prod state (drift-aware) and the full migration chain before writing; every new pgTAP file carries mandatory `set local role anon` assertions.

### Prevention rails (R2 + R4)
- **Advisors CI gate** (`24fa9d9`): daily workflow diffs live Management-API security advisors vs a committed 93-key baseline, fails on net-new WARN/ERROR. ⚠ inert until the `SUPABASE_ACCESS_TOKEN` repo secret is added.
- **Anon-row pgTAP matrix** (`2d14dbc`): 41 RLS tables — 39 anon-sees-nothing pins + 2 justified allowlist entries + 12 write denials, plus TWO rails: completeness guard (uncovered RLS table ⇒ red) and RLS-disabled guard (any public table with RLS off ⇒ red). The rail that would have caught round-1's P0-3.

### P1 (`b57ce05`)
`get_public_profiles` is_blocked filter · `is_minor` EXECUTE revoked (enumeration oracle) · `workout_comments` WITH CHECK kills author_id forgery · `enforce_profile_privileged_fields` → BEFORE INSERT OR UPDATE + email pin.

### P2 (`184d4c6`)
Completed-workout date/status freeze · workouts DELETE audit · CHECK bounds ×4 (prod data pre-scanned; 1 bad dob row clamped) · legacy pre-ensure_rls tables dropped · `client_package_events.package_id` ownership pin · `active_workouts` view gets its missing migration (drift class) · `is_admin()` uid-binding. One-active-workout index deliberately NOT applied (analysis in-file: would brick users with orphaned in_progress rows).

### Races (`9e873b4`)
`save_live_workout`: LWW predicate folded into both ON CONFLICT WHERE clauses **+ children reconciliation skipped when the shell upsert is rejected** (without this a stale concurrent sync still clobbered newer sets) · `nudge_gym_member` advisory-lock cooldown · guard-bug-classes rule pins the LWW predicate against future redefinitions · save_client_plan race dropped by design (coexist).

### Prod apply
NOT applied to prod. Owner-gated, drift-aware apply after merge (verify live → apply_migration → verify + get_advisors).

## Context
PR #209 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/209
