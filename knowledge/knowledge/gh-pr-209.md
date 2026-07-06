---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#209
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/209
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738736+00:00'
updated: '2026-07-06T21:16:37.738737+00:00'
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

Round 1 (4 P0 RLS holes + 2 GDPR data-loss) shipped in #206/#208 and is live on prod. This PR is the remaining owner-approved audit backlog — two prevention rails + P1 fixes + P2 batch + race fixes.

### Prevention rails (R2 + R4)
- **Adviso

## Details
## DB hardening round 2 (audit 2026-07-05 follow-through)

Round 1 (4 P0 RLS holes + 2 GDPR data-loss) shipped in #206/#208 and is live on prod. This PR is the remaining owner-approved audit backlog — two prevention rails + P1 fixes + P2 batch + race fixes.

### Prevention rails (R2 + R4)
- **Advisors CI gate**: daily workflow diffs live Management-API security advisors vs a committed 93-key baseline, fails on net-new WARN/ERROR.
- **Anon-row pgTAP matrix**: 41 RLS tables — 39 anon-sees-nothing pins + 2 justified allowlist entries + 12 write denials, plus completeness guard and RLS-disabled guard.

### P1
`get_public_profiles` is_blocked filter · `is_minor` EXECUTE revoked · `workout_comments` WITH CHECK kills author_id forgery · `enforce_profile_privileged_fields` → BEFORE INSERT OR UPDATE + email pin.

### P2
Completed-workout date/status freeze · workouts DELETE audit · CHECK bounds ×4 · legacy pre-ensure_rls tables dropped · `client_package_events.package_id` ownership pin · `active_workouts` view gets its missing migration · `is_admin()` uid-binding.

### Races
`save_live_workout`: LWW predicate folded into both ON CONFLICT WHERE clauses **+ children reconciliation skipped when the shell upsert is rejected** · `nudge_gym_member` advisory-lock cooldown · guard-bug-classes rule pins the LWW predicate.

## Context
PR #209 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/209
