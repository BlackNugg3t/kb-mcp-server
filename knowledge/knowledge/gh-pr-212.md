---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#212
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/212
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738701+00:00'
updated: '2026-07-06T21:16:37.738702+00:00'
confidence: high
status: active
authors:
- BlackNugg3t
depends_on: []
conflicts_with: []
related: []
---

# ci: install harnext agentic pipeline (Epic I)

## Summary
## Summary
Installs the harnext agentic dev pipeline (issue -> plan -> implement -> review -> verify, driven by Claude Code GitHub Actions), scoped to Epic I only per the harnext adoption plan. GitHub-hosted runners only (no self-hosted), default GITHUB_TOKEN (no PAT), trimmed spine vs. tarmacview's

## Details
## Summary
Installs the harnext agentic dev pipeline (issue -> plan -> implement -> review -> verify, driven by Claude Code GitHub Actions), scoped to Epic I only per the harnext adoption plan. GitHub-hosted runners only (no self-hosted), default GITHUB_TOKEN (no PAT), trimmed spine vs. tarmacview's full 13-workflow pipeline (no triage/gap/doc-gardening stages).

## Changes
- `.github/workflows/`: harnext-tagger, harnext-plan, harnext-implement, harnext-review, harnext-review-fix, harnext-verify, claude-assistant
- `.claude/skills/{grain-review,ponytail-review,review-proof}/SKILL.md` re-anchored to this repo's real exemplars
- `harness.config.json` (commands/riskTiers/protected_files)
- `.github/ISSUE_TEMPLATE/{feature,harness-gap}.md`, `.github/pull_request_template.md`, `docs/agents/issue-tracker.md`
- `.gitignore`: allowlist exceptions for the 3 new skill directories

## Risk Tier
- [x] T1 (docs/CI-config only, no application code touched)

## Context
PR #212 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/212
