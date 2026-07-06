---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#218
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/218
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620608+00:00'
updated: '2026-07-06T20:55:53.620609+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# document the three harnext review-stage skills

## Summary
Closes #214

## Summary
Adds a one-line note to `docs/agents/issue-tracker.md` (under `## Repo-specific notes`) documenting the three review skills the harnext review stage runs on the diff — `grain-review` (structural consistency / spaghetti), `ponytail-review` (over-engineering / what to cut), and

## Details
Closes #214

## Summary
Adds a one-line note to `docs/agents/issue-tracker.md` (under `## Repo-specific notes`) documenting the three review skills the harnext review stage runs on the diff — `grain-review` (structural consistency / spaghetti), `ponytail-review` (over-engineering / what to cut), and `review-proof` (test-proven correctness).

Docs-only, single-file, single-line addition. No source, workflow, or migration changes.

## Risk tier
T1

## Test plan
- [x] `git diff --stat` shows only `docs/agents/issue-tracker.md`, 1 insertion
- [x] Note names all three review skills in the review-stage context
- [x] No other files changed

## Context
PR #218 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/218
