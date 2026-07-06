---
type: knowledge
source: github
source_id: 317e105a
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/commit/317e105a1324703450c9fb540355e7a9f5926140
tags:
- enhancement
- source:github
created: '2026-07-06T21:25:28.481372+00:00'
updated: '2026-07-06T21:25:28.481372+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# perf(keep-warm): warm the real bootstrap path, not a bare createClient

## Summary
perf(keep-warm): warm the real bootstrap path, not a bare createClient

On-device profiling (2026-07-06, ?perf=1) isolated the cold-launch cost: the
bootstrap server action's actual work is trivial (~130-300ms server-side — even
the getAllWorkoutDetails month join is <200ms), and the whole ~5s first

## Details
perf(keep-warm): warm the real bootstrap path, not a bare createClient

On-device profiling (2026-07-06, ?perf=1) isolated the cold-launch cost: the
bootstrap server action's actual work is trivial (~130-300ms server-side — even
the getAllWorkoutDetails month join is <200ms), and the whole ~5s first-paint
wait is the serverless COLD-START of the action's heavy import graph (the
service-role admin client + the workout/planned/competitions/trainer/coach/gym
service modules).

The keep-warm route (pinged every ~60s by the Sentry uptime check) only did a
bare createClient(), which never loads that heavy graph — so the ping warmed the
wrong thing and the action still paid the full cold-start. This makes it invoke
bootstrapCoreData() (anonymous → returns the public payload, no per-user data),
loading the exact module graph into the shared Fluid instance so the ping keeps
the cold path genuinely warm.

## Context
Commit 317e105a in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/commit/317e105a1324703450c9fb540355e7a9f5926140
