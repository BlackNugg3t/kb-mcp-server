---
type: memory
source: discord
source_id: '1510397336004857969'
source_url: https://discord.com/channels/1510390323350736998/1510390418871816253/1510397336004857969
tags:
- bug
- source:discord
created: '2026-07-06T21:59:08.616088+00:00'
updated: '2026-07-06T21:59:08.616089+00:00'
importance: medium
decay: weekly
participants:
- fuck_the_society
context_type: discussion
related: []
---

# Bug fix: Planned kg/reps/RPE fields blank when starting live workout from a planned workout card

## Context — When & Where
Discord channel #changelog, 2026-05-30T21:39:46.729Z

## Decision / Preference / Insight
When tapping 'Spustiť tréning' (Start Workout) on a planned workout card, the live workout started with blank weight/reps/RPE inputs even though values were filled in on the plan. Root cause: cardPrimaryAction looked up the plan from currentPlans (server/write-queue state), which lagged behind the editedById overlay due to a 600ms debounce. Fix: Today's workout (dayOffset === 0) now calls handleStartWorkout(toPlannedWorkout(w)) using the Workout view model that already includes the editedById overlay. Commit: 32cf6dc.

## Rationale
UX bug — users saw blank inputs despite having filled in planned values, causing confusion when starting workouts.

## Scope & Decay
Valid until explicitly superseded by a new decision

## Related Memories
None
