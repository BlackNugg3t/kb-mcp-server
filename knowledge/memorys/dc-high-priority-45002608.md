---
type: memory
source: discord
source_id: '1511126923345002608'
source_url: https://discord.com/channels/1510390323350736998/1510402959312289822/1511126923345002608
tags:
- question
- source:discord
created: '2026-07-06T22:03:02.993398+00:00'
updated: '2026-07-06T22:03:02.993402+00:00'
importance: medium
decay: weekly
participants:
- leone9037
context_type: discussion
related: []
---

# Bug: Live training session overwritten when navigating to another day to schedule

## Context — When & Where
Discord channel #high-priority, 2026-06-01T21:58:53.906Z

## Decision / Preference / Insight
Keď máš live tréning (máš že cvičíš), prejdeš na iný deň a čas si naplánovať tréning, tak sa ti dnešný live tréning zmaže asi a dá sa ti tam ten z iného dňa, ale je stále že to cvičíš.

## Rationale
High-priority data corruption bug: active live training session is lost/replaced when user navigates to schedule a workout on a different day. The scheduled session from the other day gets placed into the current slot but still shows as 'in progress'.

## Scope & Decay
Valid until explicitly superseded by a new decision

## Related Memories
None
