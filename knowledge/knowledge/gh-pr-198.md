---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#198
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/pull/198
tags:
- enhancement
- source:github
created: '2026-07-06T21:16:37.738709+00:00'
updated: '2026-07-06T21:16:37.738709+00:00'
confidence: high
status: active
authors:
- Unkn00wnnnn
depends_on: []
conflicts_with: []
related: []
---

# perf(runtime): lazy-load list images + memoize PostCard

## Summary
Runtime-perf follow-ups (the cold-launch bundle work is in #191/#193).

## Lazy-load list/feed images
Off-screen images in scrollable lists were downloading + decoding on first render. Added `loading="lazy"` + `decoding="async"` to:
- **social `Avatar`** — every feed / search / profile row
- **compe

## Details
Runtime-perf follow-ups (the cold-launch bundle work is in #191/#193).

## Lazy-load list/feed images
Off-screen images in scrollable lists were downloading + decoding on first render. Added `loading="lazy"` + `decoding="async"` to:
- **social `Avatar`** — every feed / search / profile row
- **competition cover + card thumbnail** — the Compete list

## Memoize PostCard
`PostCard` does real work per render (muscle-load math + SVG). It wasn't memoized, and FeedTab passed it fresh inline handlers every render — so every post re-rendered whenever the feed re-rendered for unrelated reasons. Wrapped `PostCard` in `React.memo` + stabilized the handlers FeedTab passes.

## Context
PR #198 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/pull/198
