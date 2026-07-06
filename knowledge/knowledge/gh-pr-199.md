---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#199
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/199
tags:
- enhancement
- source:github
created: '2026-07-06T20:55:53.620666+00:00'
updated: '2026-07-06T20:55:53.620666+00:00'
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
The two longest lists rendered **every** row even off-screen. `content-visibility: auto` lets the browser skip layout + paint for rows outside the viewport — the cheap, no-library version of virtualization — with `contain-intrinsic-size: auto Npx` keeping the scrollbar stable (the `auto` keyword rem

## Details
The two longest lists rendered **every** row even off-screen. `content-visibility: auto` lets the browser skip layout + paint for rows outside the viewport — the cheap, no-library version of virtualization — with `contain-intrinsic-size: auto Npx` keeping the scrollbar stable (the `auto` keyword remembers each row's real height after first paint).

- **ExercisePicker** — the exercise library is 100s of rows; off-screen rows now skip render (~72px intrinsic).
- **CompetitionLeaderboard** — a big competition is 100s of ranks; same treatment (~56px), TV mode included.

**Pure CSS** (Tailwind arbitrary properties) — no JS, no dependency, no behavior change. Off-screen rows stay focusable + accessible. Verified the classes land in the built CSS.

## Gates
tsc clean · guard 0-new · my files 0 net-new lint · **1300 tests ×2** · `build:pwa` compiles (only the known preview-env prerender failure).

## Context
PR #199 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/199
