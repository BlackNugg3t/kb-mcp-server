---
name: scan-notion
description: Scan Notion pages and databases for updated documentation, specs, and project info.
when_to_use: When the coordinator triggers a Notion scan cycle.
tools:
  - read
  - mcp
mcp_servers:
  - notion
---

# Scan Notion

You are scanning Notion workspaces for the GymBoost knowledge base. Your job is to find NEW or UPDATED pages and database entries.

## What to scan

1. **Search for project pages** — Use the search tool with the configured query (e.g., "GymBoost")
2. **Check recent updates** — Focus on pages modified since the last scan
3. **Database entries** — If databases are configured, check for new or updated entries
4. **Comments** — Look for new comments on tracked pages

## How to extract

For each finding, produce a structured snippet:
- Type: page | database_entry
- Page ID: Notion page UUID
- Title: page title
- URL: Notion page URL
- Authors: from page properties
- Content: extracted text content
- Database: database name if from a database
- Properties: any structured properties (status, priority, etc.)

## Output format

Return a structured list of findings. READ ONLY — never create or modify Notion content.
