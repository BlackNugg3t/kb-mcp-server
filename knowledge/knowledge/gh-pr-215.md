---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#215
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/215
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738677+00:00'
updated: '2026-07-06T21:16:37.738678+00:00'
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
harnext-implement, harnext-review-fix, and claude-assistant are the only stages that push commits. They now prefer secrets.PAT_TOKEN (falls back to GITHUB_TOKEN if unset) so their pushes are attributed to the repo owner instead of github-actions[bot] — Vercel's Hobby plan blocks deploys triggered by

## Details
harnext-implement, harnext-review-fix, and claude-assistant are the only stages that push commits. They now prefer secrets.PAT_TOKEN (falls back to GITHUB_TOKEN if unset) so their pushes are attributed to the repo owner instead of github-actions[bot] — Vercel's Hobby plan blocks deploys triggered by any other git actor on a private repo.

## Context
PR #215 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/215
