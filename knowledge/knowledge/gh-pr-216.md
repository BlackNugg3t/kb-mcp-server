---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#216
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/216
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620627+00:00'
updated: '2026-07-06T20:55:53.620628+00:00'
confidence: high
status: active
authors:
- BlackNugg3t
depends_on: []
conflicts_with: []
related: []
---

# ci(harnext): push-performing stages authenticate as PAT_TOKEN

## Summary
## Summary
harnext-implement, harnext-review-fix, and claude-assistant are the only stages that push commits. They now prefer `secrets.PAT_TOKEN` (falls back to `GITHUB_TOKEN` if unset) so those pushes are attributed to the repo owner instead of `github-actions[bot]` — Vercel's Hobby plan blocks dep

## Details
## Summary
harnext-implement, harnext-review-fix, and claude-assistant are the only stages that push commits. They now prefer `secrets.PAT_TOKEN` (falls back to `GITHUB_TOKEN` if unset) so those pushes are attributed to the repo owner instead of `github-actions[bot]` — Vercel's Hobby plan blocks deploys triggered by any other git actor on a private repo (confirmed via the harnext dry-run on issue #211 / PR #213).

## Changes
- `harnext-implement.yml`: checkout token, implementer's github_token/GH_TOKEN, and the "Open PR" step now prefer PAT_TOKEN
- `harnext-review-fix.yml`: same, for the review-fix loop
- `claude-assistant.yml`: only the final "Commit and push" step (the only one that actually pushes)

Read-only stages (plan/review/verify/tagger) are untouched — they never push, so Vercel's actor check doesn't apply.

## Risk Tier
- [x] T1 (CI config only, no application code touched)

## Testing
- All 3 modified workflow YAMLs validated (yaml parse) before commit.
- Post-merge: re-run the pipeline against throwaway issue #214 to confirm the implement stage's push now shows the PAT's owner as actor and Vercel deploys instead of canceling.

## Context
PR #216 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/216
