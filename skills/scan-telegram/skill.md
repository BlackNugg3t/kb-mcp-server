---
name: scan-telegram
description: Scan Telegram chats for team coordination messages and technical discussions.
when_to_use: When the coordinator triggers a Telegram scan cycle.
tools:
  - read
  - mcp
mcp_servers:
  - telegram
---

# Scan Telegram

You are scanning Telegram chats for the GymBoost knowledge base. Your job is to find NEW messages since the last scan and extract meaningful information.

## What to scan

1. **Configured chats** — Scan each chat listed in config.json
2. **Message updates** — Use get_updates to find new messages since last checkpoint
3. **Replies** — Check reply chains for context

## What to look for

Same criteria as Discord:
- **Decisions** → memory items
- **Bugs** → bug tracking
- **Feature requests** → roadmap
- **Architecture discussions** → knowledge items
- **Questions with answers** → knowledge items

## How to extract

For each meaningful message, produce a structured snippet:
- Message ID: Telegram message ID
- Chat: chat name or ID
- Content: message text (trim to essence)
- Author: Telegram username or display name
- Timestamp: when sent
- Context: what was being discussed
- Type: decision | bug_report | feature_request | question | announcement | discussion

## Privacy & Scope

Only extract project-relevant information. Skip personal chatter and off-topic messages.
READ ONLY — never send messages to Telegram.
