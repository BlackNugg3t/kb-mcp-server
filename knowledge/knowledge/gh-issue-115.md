---
type: knowledge
source: github
source_id: dev-Leone/gymboost-PWA-betaa#115
source_url: https://github.com/dev-Leone/gymboost-PWA-betaa/issues/115
tags:
- bug
- source:github
created: '2026-07-06T20:46:19.372378+00:00'
updated: '2026-07-06T20:46:19.372379+00:00'
confidence: high
status: active
authors:
- dev-Leone
depends_on: []
conflicts_with: []
related: []
---

# Profile: duplicate unit label ("0 kg kg" / "0 cm cm") on empty numeric inputs

## Summary
Every empty numeric input in the profile shows a doubled unit — 0 kg kg / 0 cm cm — because the placeholder already contains the unit AND there is a sibling unit <span>. Fix: change placeholder from `0 ${unit}` to "0".

## Details
Every empty numeric input in the profile shows a doubled unit — 0 kg kg / 0 cm cm — because the placeholder already contains the unit AND there is a sibling unit <span>. Fix: change placeholder from `0 ${unit}` to "0".

## Context
Issue #115 in dev-Leone/gymboost-PWA-betaa

## Implications


## Verification


## References
https://github.com/dev-Leone/gymboost-PWA-betaa/issues/115
