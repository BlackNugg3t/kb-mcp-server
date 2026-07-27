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

# Build and start (mcp-server only — query mode, no scanning)
docker compose up -d

# Follow logs
docker compose logs -f mcp-server

# Run a one-off scan (fills knowledge/ once)
docker compose run --rm scanner-once

# Or start continuous scanning (scans immediately, then every scan_interval_minutes)
docker compose --profile kb-scan up -d scanner
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

The KB and a self-hosted GitHub Actions runner pool (registered against
`GymBOOST-team/gymboost`) run as containers on the same `kb-network`
bridge, on one dedicated Debian box — but they have **independent
lifecycles**. `./run.sh` starts the runner pool; the KB is brought up later,
whenever it's actually needed, with `./run-kb.sh`. Both scripts share the
same Compose project (derived from this directory), so they land on the
same `kb-network` regardless of which one runs first — the runner reaches
the KB by service name once it exists, no `localhost` port juggling needed.

**The runner pool has two parts:**
- `gh-runner` — one always-on, persistent (`EPHEMERAL=false`) runner. Zero
  cold-start for the common case of one job at a time.
- `runner-watcher` — polls GitHub every 30s for queued-vs-idle counts and
  `docker run`s extra `EPHEMERAL=true` "burst" runners on demand (capped at
  `GH_RUNNER_MAX_EXTRA`), one per unmet job. A burst runner registers, runs
  exactly one job, deregisters, and `--rm` removes it — true scale-to-zero,
  no idle burst containers when the queue is empty. This is how the pool
  handles more than one job (e.g. two harnext agent runs on different
  issues) at once, without paying for N always-on containers. See
  `runner/watch-queue.sh`.

Both `gh-runner` and any burst runner get the host Docker socket mounted
(`/var/run/docker.sock`) — needed by the app repo's `db-smoke.yml`, which
shells out to Docker via `supabase db start`. Deliberate tradeoff: this
grants the runner containers root-equivalent access to the host Docker
daemon.

```bash
# On the runner machine (fresh Debian box):
git clone git@github.com:BlackNugg3t/kb-mcp-server.git
cd kb-mcp-server

cp .env.example .env
vim .env   # fill in KB_AUTH_TOKEN, GH_RUNNER_PAT, GH_RUNNER_REPO_URL,
           # CLAUDE_CODE_OAUTH_TOKEN, GH_RUNNER_MAX_EXTRA (see .env.example)
           # GH_RUNNER_PAT needs Administration:RW + Actions:Read (the
           # latter is what lets runner-watcher list queued runs).

./deploy.sh   # installs Docker if missing, validates .env, builds images,
              # syncs CLAUDE_CODE_OAUTH_TOKEN to the repo's GH secrets
./run.sh      # starts gh-runner + runner-watcher

# Later, when the KB is actually needed:
./run-kb.sh           # mcp-server only — query mode, no auto-scan
./run-kb.sh --scan    # also starts continuous scanning (see note below)
```

No systemd unit is involved for this path — `restart: unless-stopped` plus
Docker's own service bring containers back after a reboot.

**Heads up: the scanner fills the KB immediately on start, not on a
schedule.** `scan-loop` runs a full scan across every enabled source
(GitHub, Notion, Discord, Telegram) *before* its first sleep — so the
`scanner` service is gated behind a Compose profile (`kb-scan`) and won't
start with a plain `docker compose up -d` or `./run-kb.sh`. Use
`docker compose run --rm scanner-once` for a single fill you control, or
`./run-kb.sh --scan` when you actually want it running continuously.

Verify:

```bash
curl http://localhost:9020/health          # once run-kb.sh has been run
docker logs -f gh-runner                   # look for "Listening for Jobs"
docker logs -f runner-watcher              # should loop quietly when idle
docker compose exec gh-runner docker ps    # confirms the socket mount works
docker compose exec gh-runner curl -sf http://kb-mcp-server:9020/health
# then check GitHub: repo -> Settings -> Actions -> Runners
```

**Tokens needed:**

| Var | Purpose |
|-----|---------|
| `GH_RUNNER_PAT` | PAT scoped to the target repo — Administration: read/write (mint/revoke registration tokens, list runners) + Actions: Read (list queued runs, for `runner-watcher`). Classic `repo` scope also works. |
| `GH_RUNNER_REPO_URL` | The repo the runner registers against, e.g. `https://github.com/GymBOOST-team/gymboost`. |
| `GH_RUNNER_MAX_EXTRA` | Safety cap on simultaneous burst runners `runner-watcher` may start (default 4). |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code OAuth token. `deploy.sh` pushes it to the repo's GitHub Actions secrets — harnext steps in workflows already reference `secrets.CLAUDE_CODE_OAUTH_TOKEN`, injected per-job by GitHub itself. The runner container never reads this value directly. |

**Why does `runner-watcher` poll, when a real runner's `Runner.Listener`
already long-polls GitHub for its own jobs?** Different concern. Each
runner's own long-poll only tells *that* runner about jobs assigned to it —
it has no visibility into total queue depth. Deciding "there are more
queued jobs than idle runners, start another one" needs an outside view of
the queue, which only the Actions API exposes — hence `runner-watcher`
polling `GET .../actions/runs?status=queued` and `.../actions/runners`
separately. `gh-runner` itself is unchanged: still one persistent
long-poll connection, no interval to configure, not "spamming" GitHub.

This infra is separate from actually moving any workflow off
`ubuntu-latest` — switching a stage to this runner (e.g. adding a
`self-hosted` label to `runs-on:` in `harnext-verify.yml`) is a per-workflow
decision made in the app repo, tracked in that repo's runner-migration
plan.

---

## Deployment

### Docker Compose (Recommended)

KB server only, no runner:

```bash
# 1. Clone the repo
git clone https://github.com/your-org/gymboost-knowledge-base.git
cd gymboost-knowledge-base

# 2. Configure
cp .env.example .env
# Edit .env with your tokens
python -c "import secrets; print(secrets.token_urlsafe(32))"  # generate auth token

# 3. Start (MCP server only — query mode, no scanning)
docker compose up -d

# 4. Verify
docker compose logs mcp-server
docker compose exec mcp-server python -m pytest tests/ -q
```

Services:
| Service | Profile | Purpose |
|---------|---------|---------|
| `mcp-server` | default | Long-running MCP server (HTTP on :9020) |
| `scanner` | `kb-scan` | Periodic scan loop — scans immediately on start, then every `scan_interval_minutes`. Opt-in: `docker compose --profile kb-scan up -d scanner` |
| `scanner-once` | `manual` | One-off scan: `docker compose run --rm scanner-once` |
| `gh-runner` | overlay (`docker-compose.runner.yml`) | Self-hosted GitHub Actions runner — see [GitHub Runner Setup](#github-runner-setup) for the full `deploy.sh` / `run.sh` / `run-kb.sh` flow. |

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
├── docker-compose.runner.yml # Self-hosted GitHub Actions runner overlay
├── deploy.sh                # One-time bootstrap (Docker install, .env checks, image build)
├── run.sh                   # Starts gh-runner only
├── run-kb.sh                # Starts the KB later (mcp-server, optional --scan)
├── runner/Dockerfile         # gh-runner image (myoung34/github-runner + gh CLI)
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
