---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#213
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/213
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738685+00:00'
updated: '2026-07-06T21:16:37.738686+00:00'
confidence: high
status: active
authors:
- github-actions[bot]
depends_on: []
conflicts_with: []
related: []
---

# add readme note pointing to harnext pipeline docs

## Summary
Closes #211

## Summary
Adds a short `## Agentic pipeline` note near the top of `README.md` pointing readers to [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md) for how the harnext pipeline (plan → implement → review → verify) works. Docs-only, no runtime change.

## Risk tier
T1 (docs

## Details
Closes #211

## Summary
Adds a short `## Agentic pipeline` note near the top of `README.md` pointing readers to [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md) for how the harnext pipeline (plan → implement → review → verify) works. Docs-only, no runtime change.

## Risk tier
T1 (docs only)

## Test plan
- [x] `git diff --stat` shows exactly one file (`README.md`) changed, additions only (+4)
- [x] Link target `docs/agents/issue-tracker.md` exists at repo root
- [x] No code/test/config/migration surface touched — no gate required for docs-only

## Context
PR #213 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/213
