# 🧠 GymBoost Knowledge Base MCP Server

Multi-source knowledge base system that periodically scans **GitHub**, **Notion**, **Discord**, and **Telegram** for new information, indexes findings using structured templates, and exposes search/query capabilities via the **Model Context Protocol (MCP)**.

Built for the **GymBoost PWA** project to give coding agents (Claude, Cursor, Harnext CLI) immediate access to the project's collective knowledge — issues, decisions, specs, and discussions.

---

## Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
  - [Native (Python)](#native-python)
  - [Docker](#docker)
- [Configuration Reference](#configuration-reference)
  - [Service Priority & Scan Intervals](#service-priority--scan-intervals)
  - [Source Origin Tags](#source-origin-tags)
  - [Authentication](#authentication)
- [MCP Tools](#mcp-tools-for-coding-agents)
- [Security](#security)
  - [Authentication](#authentication-1)
  - [Path Traversal Protection](#path-traversal-protection)
  - [Rate Limiting](#rate-limiting)
  - [Activity Audit Log](#activity-audit-log)
  - [Secrets Handling](#secrets-handling)
- [CI/CD Integration](#cicd-integration)
  - [GitHub Actions](#github-actions)
  - [GitHub Runner Setup](#github-runner-setup)
- [Deployment](#deployment)
  - [Docker Compose (Recommended)](#docker-compose-recommended)
  - [Systemd (Linux)](#systemd-linux)
- [Adding a New Service Scanner](#adding-a-new-service-scanner)
- [Knowledge Pipeline](#knowledge-pipeline)
- [Directory Structure](#directory-structure)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
External Services                    KB MCP Server                      Coding Agents
─────────────────                    ──────────────                      ──────────────
  GitHub ────┐                   ┌──────────────────┐                 ┌──────────────┐
  Notion ────┤─── Scanner ──────▶│  Coordinator     │──── MCP ──────▶│  Claude       │
  Discord ───┤    Agents          │  + Indexer       │ (stdio/HTTP)   │  Cursor       │
  Telegram ──┘   (read-only)      │  + Diff Engine    │                │  Harnext CLI  │
                                  │  + Activity Log  │◀──── HTTP ────│  GitHub Agent │
                                  │  + Auth/Rate-Lim │   POST /mcp    └──────────────┘
                                  └────────┬─────────┘
                                           │
                                    ┌──────▼──────┐
                                    │  knowledge/ │  ← Filesystem storage
                                    │  index.json │     (markdown + JSON)
                                    │  *.md       │     versioned via git
                                    │  logs/      │     activity.jsonl
                                    └─────────────┘

Transport Modes:
  stdio — Local agents (Claude, Cursor) connect via standard I/O pipe
  SSE/HTTP — Remote agents (GitHub Actions) connect via POST http://host:9020/mcp
  Both modes share the same coordinator, indexer, and knowledge store.
```

## Quick Start

### Native (Python)

```bash
cd /data/code/gymboost/kb-mcp-server

# Prerequisites: Python 3.11+, Node.js 20+
pip install -r requirements.txt

# Generate an auth token
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set up environment
cp .env.example .env
# Edit .env — add KB_AUTH_TOKEN, GITHUB_TOKEN, etc.

# Start the MCP server (mode from config.json — auto-detects stdio or sse)
python -m src.main serve

# The server is now listening:
#   stdio mode: reads/writes via stdin/stdout
#   HTTP mode:  http://127.0.0.1:9020/mcp  (set mode: "sse" in config)
```

### Docker

```bash
cd /data/code/gymboost/kb-mcp-server

# Create .env with your tokens
cp .env.example .env
vim .env  # add KB_AUTH_TOKEN, GITHUB_TOKEN, etc.

# Build and start
docker compose up -d

# Follow logs
docker compose logs -f mcp-server

# Run a one-off scan
docker compose run --rm scanner-once
```

---

## Configuration Reference

All configuration lives in `config.json`. Environment variables are resolved from `${VAR}` placeholders.

### Top-Level Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scan_interval_minutes` | int | `30` | Fallback interval for scan-loop |
| `scan_jitter_seconds` | int | `60` | Random jitter added to scan timing |
| `mcp_server.auth_token` | string | `""` | Token agents must provide to connect |
| `mcp_server.rate_limit_rescan_seconds` | int | `300` | Min seconds between rescans |
| `logging.debug` | bool | `false` | Enable verbose debug logging |
| `logging.activity_log_file` | string | `"logs/activity.jsonl"` | Persistent audit log path |

### Service Priority & Scan Intervals

Each service has independent `priority` and `check_interval_minutes`:

| Service | Priority | Interval | Rationale |
|---------|----------|----------|-----------|
| GitHub | 10 | 15 min | Issues/PRs change rapidly — highest priority |
| Notion | 8 | 30 min | Docs change moderately |
| Discord | 6 | 60 min | Chat is ephemeral — lower frequency |
| Telegram | 5 | 60 min | Chat is ephemeral — lower frequency |

**Priority**: 1-10, higher = scanned first in each cycle.
**check_interval_minutes**: Minimum time between scans for that source. If not due yet, the source is skipped.

### Source Origin Tags

Every persisted knowledge item automatically gets a `source:{service_name}` tag (e.g., `source:github`, `source:notion`). This allows filtering queries by origin:

```
# Search GitHub-originated knowledge only
search_kb source=github query="security"
```

### Authentication

Set `KB_AUTH_TOKEN` in your environment (or in `.env`):

```bash
# Generate a secure token
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: xK3mP9vR2nQ7wJ5tY8bA1cF4hL6oZ0sD...

# Add to .env
echo "KB_AUTH_TOKEN=xK3mP9vR2nQ7wJ5tY8bA1cF4hL6oZ0sD" >> .env
```

In `config.json`, the MCP server section references it:
```json
"mcp_server": {
  "auth_token": "${KB_AUTH_TOKEN}",
  "rate_limit_rescan_seconds": 300
}
```

When auth is configured, all MCP `initialize` requests must include the token.

---

## MCP Tools (for coding agents)

### Query Tools

| Tool | Description | Example |
|------|-------------|---------|
| `search_kb` | Full-text + tag search across all knowledge | `search_kb query="login bug" tags=["security"] source="github"` |
| `get_knowledge` | Retrieve a specific item by ID (returns full markdown) | `get_knowledge item_id="gh-issue-106"` |
| `list_tags` | List all tags with item counts | `list_tags` |
| `list_sources` | List all sources with stats, scan timestamps | `list_sources` |
| `get_kb_stats` | Overall KB statistics with per-source scan times | `get_kb_stats` |

### Admin Tools

| Tool | Description | Example |
|------|-------------|---------|
| `rescan_kb` | Trigger immediate knowledge refresh from sources (rate-limited) | `rescan_kb source="github"` or `rescan_kb` (all) |
| `reload_index` | Reload the KB index from disk | `reload_index` |

---

## Security

### Authentication

- **MCP server** requires an `auth_token` (set via `KB_AUTH_TOKEN` env var) for `initialize` handshake
- Without a token configured, the server runs in **dev mode** (open to any local connection)
- **Production**: Always set `KB_AUTH_TOKEN`. Generate with `secrets.token_urlsafe(32)`.

### Path Traversal Protection

All file system paths are validated to prevent directory traversal attacks:
- `make_file_path()` sanitizes entry IDs (strips `/`, `\`, `..`, null bytes)
- `get_knowledge()` resolves the final path and verifies it stays within the knowledge base root
- All paths are normalized with `Path.resolve()` and checked with a prefix guard

### Rate Limiting

- `rescan_kb` is rate-limited (default: 1 call per 300 seconds per server instance)
- Query tools (`search_kb`, `get_knowledge`, etc.) are NOT rate-limited (designed for agent use)
- Rate limit can be configured via `mcp_server.rate_limit_rescan_seconds` in `config.json`

### Activity Audit Log

Every significant action is logged to `logs/activity.jsonl` (JSON Lines format):
- **Server lifecycle**: start, client connect, shutdown
- **MCP tool calls**: which tool, arguments (minus sensitive index_path), result, duration
- **Scan events**: per-source scan results, errors, skipped sources
- **Errors**: component, message, context

Example entry:
```json
{"timestamp":"2026-07-06T15:30:00Z","type":"mcp_call","pid":1234,"tool":"search_kb","args":{"query":"bug"},"result":"5 results","duration_ms":12.3,"success":true}
```

The activity log auto-rotates at 50MB and keeps 5 backups.

### Secrets Handling

- `.env` is in `.gitignore` AND `.dockerignore` — never committed
- Activity logger strips keys named `token`, `api_key`, `auth`, `secret`, `password`, `credential`
- `config.json` uses `${VAR}` placeholders — resolved at runtime, never stored in plaintext
- Scanner agents are **read-only** — no write/edit/bash tools

---

## CI/CD Integration

The KB MCP server runs on a dedicated server (not in GitHub Actions to avoid burning minutes). GitHub Actions agents connect to it via HTTP. For private runners, both can run on the same machine.

### Architecture for Private Runners

```
Same Machine (Private Runner)
├── KB MCP Server (HTTP on :9020)
│   ├── Scanner loop (internal)
│   └── Coordinator + Indexer
│
├── GitHub Actions Runner
│   └── Agent queries KB via curl http://localhost:9020/mcp
│
└── Local Claude/Cursor
    └── Connects via stdio (direct pipe)
```

### GitHub Actions — Query the KB

```yaml
# .github/workflows/agent-with-kb.yml
name: Agent with KB Access

on:
  workflow_dispatch:
  issues:
    types: [opened, labeled]

jobs:
  agent:
    runs-on: self-hosted  # Same machine as KB server

    steps:
      - uses: actions/checkout@v4

      - name: Query knowledge base for context
        id: kb
        run: |
          RESPONSE=$(curl -s -X POST http://localhost:9020/mcp \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer ${{ secrets.KB_AUTH_TOKEN }}" \
            -d '{
              "jsonrpc": "2.0",
              "id": 1,
              "method": "tools/call",
              "params": {
                "name": "search_kb",
                "arguments": {
                  "query": "${{ github.event.issue.title }}",
                  "limit": 10
                }
              }
            }')

          echo "KB_RESULT=$RESPONSE" >> $GITHUB_OUTPUT

      - name: Use KB context
        run: |
          echo "Found relevant knowledge:"
          echo "${{ steps.kb.outputs.KB_RESULT }}" | jq .

  kb-scan:
    runs-on: self-hosted
    if: github.event_name == 'schedule'
    steps:
      - name: Trigger KB rescan
        run: |
          curl -s -X POST http://localhost:9020/mcp \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer ${{ secrets.KB_AUTH_TOKEN }}" \
            -d '{
              "jsonrpc": "2.0",
              "id": 1,
              "method": "tools/call",
              "params": {
                "name": "rescan_kb",
                "arguments": {"source": "github"}
              }
            }'
```

### GitHub Runner Setup

For self-hosted runners that need persistent KB access:

```bash
# On the runner machine
cd /opt/gymboost-kb
git clone https://github.com/your-org/gymboost-knowledge-base.git .

# Configure
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"  # generate auth token
# Add token to .env as KB_AUTH_TOKEN

# Install as systemd service (HTTP mode)
sudo cp systemd/kb-mcp-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kb-mcp-server

# Verify HTTP endpoint
curl http://localhost:9020/health
# → {"status":"healthy","server":"gymboost-knowledge-base","version":"1.0.0","auth_enabled":true}

# GitHub Actions on the same machine can now query:
curl -s -X POST http://localhost:9020/mcp \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_kb","arguments":{"query":"test"}}}'
```

---

## Deployment

### Docker Compose (Recommended)

```bash
# 1. Clone the repo
git clone https://github.com/your-org/gymboost-knowledge-base.git
cd gymboost-knowledge-base

# 2. Configure
cp .env.example .env
# Edit .env with your tokens
python -c "import secrets; print(secrets.token_urlsafe(32))"  # generate auth token

# 3. Start (MCP server + periodic scanner)
docker compose up -d

# 4. Verify
docker compose logs mcp-server
docker compose exec mcp-server python -m pytest tests/ -q
```

Services:
| Service | Profile | Purpose |
|---------|---------|---------|
| `mcp-server` | default | Long-running MCP server (HTTP on :9020) |
| `scanner` | default | Periodic scan loop |
| `scanner-once` | `manual` | One-off scan: `docker compose run --rm scanner-once` |

### Testing the HTTP Endpoint

```bash
# Health check
curl http://localhost:9020/health

# Initialize MCP connection
curl -s -X POST http://localhost:9020/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# Search the knowledge base
curl -s -X POST http://localhost:9020/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_kb","arguments":{"query":"security","limit":5}}}'
```

### Systemd (Linux)

```bash
sudo cp systemd/kb-mcp-server.service /etc/systemd/system/
sudo cp systemd/kb-scanner.service /etc/systemd/system/
sudo cp systemd/kb-scanner.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now kb-mcp-server kb-scanner.timer

# Monitor
journalctl -u kb-mcp-server -f
journalctl -u kb-scanner -f
```

---

## Adding a New Service Scanner

See **[AGENTS.md](AGENTS.md)** for the complete agent creation template with copy-paste class template, checklist, and conventions.

Quick overview:
1. Add `Source` enum value to `src/storage/models.py`
2. Create scanner class in `src/agents/{name}_scanner.py` (extend `BaseScannerAgent`)
3. Register in `SCANNER_REGISTRY` dict in `src/coordinator.py`
4. Add config entry in `config.json` with `priority` and `check_interval_minutes`
5. Create skill manifest in `skills/scan-{name}/skill.md`
6. Write tests in `tests/test_scanners.py`

All scanners are **read-only** — they never modify the source system.

---

## Knowledge Pipeline

1. **Scan** — Each scanner agent queries its external service (read-only, via MCP)
2. **Extract** — Raw findings classified as `Knowledge`, `Memory`, or `Artifact`
3. **Diff** — Compared against existing index (new/updated/unchanged/removed/duplicate)
4. **Index** — New/updated items written to markdown files with YAML frontmatter
5. **Tag** — Automatic `source:{name}` tag applied + inferred tags from content
6. **Persist** — `index.json` updated with metadata, cross-references, scan stats
7. **Commit** — Changes committed to git for audit trail

## Directory Structure

```
kb-mcp-server/
├── config.json              # Service configuration
├── system_prompt.md         # Coordinator agent system prompt
├── AGENTS.md                # Agent creation template + guidelines
├── README.md                # This file
├── Dockerfile               # Multi-stage container build
├── docker-compose.yml       # Docker services (server + scanner)
├── docker-compose.prod.yml  # Production overrides
├── .dockerignore            # Docker build exclusions
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata + tool config
├── src/
│   ├── main.py              # Entry point (serve/scan/scan-loop)
│   ├── coordinator.py       # Central orchestrator
│   ├── config.py            # Config loader + models
│   ├── agents/              # Scanner agents
│   │   ├── base.py          # Abstract base scanner
│   │   ├── github_scanner.py
│   │   ├── notion_scanner.py
│   │   ├── discord_scanner.py
│   │   └── telegram_scanner.py
│   ├── mcp_server/          # MCP server implementation
│   │   ├── server.py        # JSON-RPC server (auth, rate-limit, logging)
│   │   ├── http_server.py   # HTTP/SSE transport for remote agents
│   │   ├── tools.py         # Tool definitions + handlers
│   │   └── activity_logger.py  # Persistent structured audit log
│   └── storage/             # Storage layer
│       ├── models.py        # Pydantic data models
│       ├── indexer.py       # Index read/write/search
│       └── diff.py          # Change detection + dedup
├── skills/                  # Harnext scanner skill manifests
│   ├── scan-github/
│   ├── scan-notion/
│   ├── scan-discord/
│   └── scan-telegram/
├── knowledge/               # Live knowledge store (auto-created)
│   ├── index.json           # Master index
│   ├── knowledge/           # Knowledge markdown files
│   ├── memories/            # Memory markdown files
│   └── artifacts/           # Artifact markdown files
├── logs/                    # Runtime logs (auto-created)
│   ├── kb-mcp-server.log    # Application log
│   └── activity.jsonl       # Persistent audit log
├── systemd/                 # systemd service + timer units
├── tests/                   # Test suite
│   ├── test_config.py
│   ├── test_diff.py
│   ├── test_indexer.py
│   ├── test_http_server.py
│   └── test_scanners.py
```

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (37 tests: config, diff, indexer, scanners, http)
pytest

# Run with coverage
pytest --cov=src --cov-report=term

# Lint
ruff check src/

# Type check
mypy src/
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Invalid auth token" | `KB_AUTH_TOKEN` not set or mismatched | Set in `.env` and restart server |
| "Path traversal denied" | Entry ID contains `../` or similar | IDs auto-sanitized; this is a security block |
| "Rate limited" on rescan | Called `rescan_kb` too quickly | Wait for `rate_limit_rescan_seconds` (default 300s) |
| Scanner returns empty results | Harnext SDK not installed or no credentials | Install `harnext` package, verify API tokens |
| "No scanner for X" | Scanner not implemented for that service | See [AGENTS.md](AGENTS.md) to add a new scanner |
| Activity log not being written | `logs/` directory permissions | Ensure `logs/` is writable by the process user |
| "Connection refused" on :9020 | Server not running or not in HTTP mode | Check `mcp_server.mode` is `"sse"` in config.json |
| "401 Unauthorized" via HTTP | Missing or wrong `Authorization` header | Use `Authorization: Bearer YOUR_TOKEN` |

---

## License

MIT
