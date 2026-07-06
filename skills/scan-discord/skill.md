---
name: scan-discord
description: Scan Discord channels for team discussions, decisions, and technical conversations.
when_to_use: When the coordinator triggers a Discord scan cycle.
tools:
  - read
  - mcp
mcp_servers:
  - discord
---

# Scan Discord

You are scanning Discord channels for the GymBoost knowledge base. Your job is to find NEW messages since the last scan and extract meaningful information.

## What to scan

1. **Configured channels** — Scan each channel listed in config.json
2. **Message history** — Read messages since the last scan timestamp
3. **Thread replies** — Check threads for extended discussions
4. **Pinned messages** — Always check pins for important announcements

## What to look for

- **Decisions**: "Let's go with X..." — extract as memory items
- **Bugs**: "The app crashes when..." — flag for bug tracking
- **Feature requests**: "It would be great if..." — extract for roadmap
- **Architecture discussions**: Technical decisions about the codebase
- **Questions with answers**: Q&A that reveals project knowledge

## How to extract

For each meaningful message, produce a structured snippet:
- Message ID: Discord message ID
- Channel: channel name
- Content: message text (trim to essence)
- Author: Discord username
- Timestamp: when sent
- Context: what was being discussed
- Type: decision | bug_report | feature_request | question | announcement | discussion

## Privacy & Scope

Only extract project-relevant information. Skip personal chatter, memes, and off-topic messages.
READ ONLY — never send messages to Discord.
