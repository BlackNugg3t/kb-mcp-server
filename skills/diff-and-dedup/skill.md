---
name: diff-and-dedup
description: Compare new scan findings against the existing index — detect new, updated, unchanged, and duplicate items.
when_to_use: After classification, before writing new items to disk.
tools:
  - read
  - edit
---

# Diff and Deduplicate

You are comparing newly extracted knowledge items against the existing knowledge base to avoid duplication and detect changes.

## Procedure

1. **Load the master index** — Read knowledge/index.json

2. **For each incoming item**:
   a. Look up by ID in the index
   b. **If found with same hash** → mark as UNCHANGED, skip
   c. **If found with different hash** → mark as UPDATED, compute what changed
   d. **If not found** → check for near-duplicates:
      - Compare title similarity (SequenceMatcher)
      - If >85% similar to an existing item → flag as POTENTIAL DUPLICATE, add as "related" reference instead of creating new
      - Otherwise → mark as NEW

3. **Detect removed items**:
   - Items in the index that no longer appear in the source → mark as STALE (don't delete, just add "stale" status)

4. **Output a diff summary**:
   ```
   Source: github
     New: 3 items
     Updated: 2 items
     Unchanged: 15 items
     Duplicates skipped: 1
     Stale (removed from source): 0
   ```

## Anti-duplication

Near-duplicate definition: Two items from the same source with >85% title similarity AND >80% content similarity.

When a near-duplicate is found:
1. Add the existing item's ID to the new item's "related" field
2. Update the existing item to mention the new source reference
3. Skip creating a standalone entry for the duplicate
