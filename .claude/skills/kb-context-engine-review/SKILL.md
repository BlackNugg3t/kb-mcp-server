---
name: kb-context-engine-review
description: >-
  Reviews a knowledge-base / context-engine project that exposes an MCP (Model
  Context Protocol) server and integrates with GitHub, Notion, Discord, and
  Telegram, typically implemented in Python and shipped via Docker. Use this
  skill whenever the user asks to review, audit, debug, harden, or PR-check
  code in this stack — even if they only mention one piece of it (e.g. "check
  my MCP server", "review the Discord bot", "audit the Notion sync", "look at
  the Dockerfile"), since these projects are usually one integrated codebase.
  Trigger on mentions of MCP server/tools/resources, context engine,
  retrieval/embedding pipeline, knowledge base ingestion, or any of
  GitHub/Notion/Discord/Telegram bot or webhook code in a Python+Docker repo.
  Also trigger for "is this production ready", "find bugs", "security
  review", or "why isn't my sync/bot working" on this kind of project.
---

# KB Context Engine + MCP Integrations Review

A structured review workflow for a Python/Docker project that combines:
1. A **knowledge-base / context engine** (ingestion, chunking, embedding, retrieval)
2. An **MCP server** exposing tools/resources to Claude or other MCP clients
3. **Integration adapters** for GitHub, Notion, Discord, and Telegram

Most bugs and security issues in this stack cluster around the seams — where data
crosses from one of these subsystems into another (webhook → queue → embedder,
or MCP tool call → external API). Review the seams first, then the internals.

## How to run this review

1. **Map the repo** before reading line-by-line.
2. **Triage which subsystems are in scope** (the user may only want one integration reviewed — don't force a full audit if they asked for the Discord bot specifically).
3. Walk the relevant checklist(s) below.
4. Report findings grouped by severity (Blocking / Should-fix / Nit), each with file:line and a one-line fix suggestion. Don't just narrate — show the fix as a diff or short code block when it's a one-liner.
5. If you find more than ~15 issues, stop and summarize the top 5 blocking ones first, then ask if the user wants the full list — don't dump an overwhelming wall of text.

## Step 1: Map the repo

Run this before anything else, to build a mental model instead of guessing at structure:

```bash
# Structure
find . -type f -name "*.py" | grep -v -E "(venv|__pycache__|\.git)" | sort
find . -maxdepth 2 -iname "docker*"
find . -iname "*.env*" -o -iname "*.yml" -o -iname "*.yaml" | grep -v node_modules

# Dependency surface
cat requirements.txt pyproject.toml 2>/dev/null

# Where's the MCP server entrypoint?
grep -rl "mcp.server\|FastMCP\|@server.call_tool\|@tool(" --include="*.py" .

# Where are the integration adapters?
grep -rli "notion_client\|discord.py\|nextcord\|python-telegram-bot\|PyGithub\|Github(" --include="*.py" .
```

Identify and note:
- Entrypoint(s) — is it one process or separate services per integration?
- How config/secrets flow in (env vars, `.env`, secret manager, hardcoded — flag hardcoded immediately)
- The ingestion → storage → retrieval path for the context engine
- Which integrations are inbound (webhooks/bots receiving events) vs outbound (API calls the engine makes)

## Step 2: Subsystem checklists

Read the relevant reference file(s) based on what's in scope. Don't load all four if the user only asked about one integration.

- `references/mcp-server.md` — MCP server/tool/resource implementation
- `references/context-engine.md` — ingestion, chunking, embeddings, retrieval quality
- `references/integrations.md` — GitHub, Notion, Discord, Telegram specifics (auth, rate limits, webhook verification)
- `references/python-docker.md` — general Python hygiene, Dockerfile, docker-compose, secrets handling

## Step 3: Cross-cutting concerns (always check these regardless of scope)

- **Secrets**: any API key/token/webhook secret committed to the repo, logged, or printed? `grep -rn "sk-\|xoxb-\|Bearer \|token=" --include="*.py"` as a starting point, then check `.env.example` isn't actually `.env`.
- **Idempotency**: do webhook handlers (Discord interaction, Telegram update, GitHub event, Notion webhook) safely handle duplicate/replayed deliveries? Most of these providers *will* redeliver.
- **Async correctness**: mixing blocking I/O (`requests`, sync DB calls) inside `async def` handlers is the single most common bug in this stack — check Discord/Telegram handlers especially.
- **Failure isolation**: does an error in one integration adapter (e.g. Notion sync failing) crash the whole process, including the MCP server and other bots? These should generally be isolated (separate containers/processes or at least separate tasks with their own error boundaries).
- **Rate limits & backoff**: does each outbound client (GitHub, Notion, Discord, Telegram) have retry/backoff on 429s, or will it get the bot/token rate-limited or banned?

## Reporting format

For each finding:
```
[BLOCKING|SHOULD-FIX|NIT] <file>:<line> — <one-line description>
Why it matters: <1-2 sentences>
Fix: <diff or short snippet, if trivial>
```

End with a short summary: what's solid, what's the single most important thing to fix before shipping.
