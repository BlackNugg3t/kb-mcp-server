---
name: index-knowledge
description: Classify and index new knowledge items — determine type, tags, and write to filesystem using templates.
when_to_use: After a scan produces raw findings, before persisting to the knowledge base.
tools:
  - read
  - write
  - edit
---

# Index Knowledge

You are classifying raw scan findings into structured knowledge base items. Use the templates to format each item correctly.

## Classification rules

### Knowledge (use templates/knowledge.md)
- Verifiable facts about the project
- Bug descriptions with reproduction steps
- Feature specifications
- Architecture decisions that are documented
- API contracts, database schemas

### Memory (use templates/memory.md)
- "Sam said we should..."
- Team decisions from chat discussions
- Preferences expressed by team members
- Conversation outcomes
- Design rationale discussed but not formally documented

### Artifact (use templates/artifact.md)
- Code snippets worth preserving
- Configuration files
- Diagrams
- Generated reports or analysis
- Log outputs from debugging sessions

## Procedure

1. For each raw finding:
   a. Read the content carefully
   b. Determine the correct type (knowledge/memory/artifact)
   c. Generate a unique ID following the convention
   d. Assign tags from the taxonomy only
   e. Rate confidence: HIGH (explicitly stated) / MEDIUM (reasonable inference) / LOW (speculation)
   f. Fill in ALL template fields — don't leave blanks

2. Write each item to:
   - knowledge/knowledge/{id}.md for knowledge
   - knowledge/memories/{id}.md for memories
   - knowledge/artifacts/{id}.md for artifacts

3. Update knowledge/index.json:
   - Add new entries
   - Update modified entries
   - Rebuild tag index

## Quality checks

- Every item has at least 1 tag, at most 5
- All tags are from the approved taxonomy
- Summaries are self-contained (understandable without reading details)
- References include exact URLs, not vague pointers
