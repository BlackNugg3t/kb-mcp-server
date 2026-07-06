---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#199
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/199
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738717+00:00'
updated: '2026-07-06T21:16:37.738717+00:00'
confidence: high
status: active
authors:
- Unkn00wnnnn
depends_on: []
conflicts_with: []
related: []
---

# perf(lists): content-visibility on long exercise + leaderboard lists

## Summary
The two longest lists rendered **every** row even off-screen. `content-visibility: auto` lets the browser skip layout + paint for rows outside the viewport with `contain-intrinsic-size: auto Npx` keeping the scrollbar stable.

- **ExercisePicker** — the exercise library is 100s of rows; off-screen r

## Details
The two longest lists rendered **every** row even off-screen. `content-visibility: auto` lets the browser skip layout + paint for rows outside the viewport with `contain-intrinsic-size: auto Npx` keeping the scrollbar stable.

- **ExercisePicker** — the exercise library is 100s of rows; off-screen rows now skip render (~72px intrinsic).
- **CompetitionLeaderboard** — a big competition is 100s of ranks; same treatment (~56px), TV mode included.

**Pure CSS** (Tailwind arbitrary properties) — no JS, no dependency, no behavior change.

## Context
PR #199 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/199
