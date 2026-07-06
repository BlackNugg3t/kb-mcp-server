# 🧠 GymBoost Knowledge Base MCP Server

Multi-source knowledge base system that periodically scans **GitHub**, **Notion**, **Discord**, and **Telegram** for new information, indexes findings using structured templates, and exposes search/query capabilities via the **Model Context Protocol (MCP)**.

Built with the [Harnext SDK](https://www.harnext.dev/docs) for Python.

## Architecture

```
External Services                    KB MCP Server                      Coding Agents
─────────────────                    ──────────────                      ──────────────
  GitHub ────┐                   ┌──────────────────┐                 ┌──────────────┐
  Notion ────┤─── Scanner ──────▶│  Coordinator     │──── MCP ──────▶│  Claude       │
  Discord ───┤    Agents          │  + Indexer       │   (stdio)      │  Cursor       │
  Telegram ──┘   (read-only)      │  + Diff Engine   │                │  Harnext CLI  │
                                  │  + MCP Server    │                └──────────────┘
                                  └────────┬─────────┘
                                           │
                                    ┌──────▼──────┐
                                    │  knowledge/ │  ← Filesystem storage
                                    │  index.json │     (markdown + JSON)
                                    │  *.md       │     versioned via git
                                    └─────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+ (for MCP server bridges)
- API tokens for services you want to scan

### Installation

```bash
cd /data/code/gymboost/kb-mcp-server

# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API tokens

# Edit config.json to configure which services to scan
```

### Usage

```bash
# Start the MCP server (for coding agents to connect)
python -m src.main serve

# Run a single scan cycle
python -m src.main scan

# Run continuous scan loop
python -m src.main scan-loop
```

### Systemd Service

```bash
# Install systemd units
sudo cp systemd/kb-mcp-server.service /etc/systemd/system/
sudo cp systemd/kb-scanner.service /etc/systemd/system/
sudo cp systemd/kb-scanner.timer /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable kb-mcp-server.service
sudo systemctl enable kb-scanner.timer
sudo systemctl start kb-mcp-server.service
sudo systemctl start kb-scanner.timer

# Check status
sudo systemctl status kb-mcp-server
journalctl -u kb-mcp-server -f
```

## Configuration

All configuration lives in `config.json`:

| Section | Description |
|---------|-------------|
| `llm` | LLM provider settings for the coordinator agent |
| `mcp_server` | MCP server mode/destination settings |
| `services.github` | GitHub repos to scan, MCP server config |
| `services.notion` | Notion workspace, databases to scan |
| `services.discord` | Discord channels to monitor |
| `services.telegram` | Telegram chats to monitor |
| `storage` | Filesystem paths for knowledge storage |
| `tags.taxonomy` | Approved tag list |
| `logging` | Log level, format, output |

## Knowledge Types

| Type | Template | Use For |
|------|----------|---------|
| **Knowledge** | `templates/knowledge.md` | Stable facts, architecture decisions, bug descriptions, specs |
| **Memory** | `templates/memory.md` | Conversation context, team decisions, preferences, discussions |
| **Artifact** | `templates/artifact.md` | Code snippets, configs, diagrams, generated files |

## MCP Tools (for coding agents)

| Tool | Description |
|------|-------------|
| `search_kb` | Full-text + tag search across all knowledge |
| `get_knowledge` | Retrieve a specific item by ID (full markdown) |
| `list_tags` | List all tags with item counts |
| `list_sources` | List all sources with statistics |
| `get_kb_stats` | Overall knowledge base statistics |

## Scanner Agents

Each scanner is a **read-only** Harnext agent connected to its source via MCP:

- **GitHub Scanner** (`src/agents/github_scanner.py`) — Issues, PRs, commits
- **Notion Scanner** (`src/agents/notion_scanner.py`) — Pages, databases
- **Discord Scanner** (`src/agents/discord_scanner.py`) — Channel messages
- **Telegram Scanner** (`src/agents/telegram_scanner.py`) — Chat messages

## Skills

Skills are reusable instruction bundles loaded by the coordinator:

- `skills/scan-github/skill.md` — GitHub scanning instructions
- `skills/scan-notion/skill.md` — Notion scanning instructions
- `skills/scan-discord/skill.md` — Discord scanning instructions
- `skills/scan-telegram/skill.md` — Telegram scanning instructions
- `skills/index-knowledge/skill.md` — Classification & indexing pipeline
- `skills/diff-and-dedup/skill.md` — Change detection & deduplication

## Pipeline

1. **Scan** — Each scanner agent queries its external service (read-only)
2. **Extract** — Raw findings are classified as knowledge/memory/artifact
3. **Diff** — New findings compared against existing index
4. **Index** — New/updated items written to markdown files
5. **Persist** — `index.json` updated with metadata
6. **Commit** — Changes committed to git for audit trail

## Directory Structure

```
kb-mcp-server/
├── config.json              # Service configuration
├── system_prompt.md         # Coordinator agent system prompt
├── src/
│   ├── main.py              # Entry point (serve/scan/scan-loop)
│   ├── coordinator.py       # Central orchestrator
│   ├── config.py            # Config loader
│   ├── agents/              # Scanner agents
│   ├── mcp_server/          # MCP server + tool definitions
│   └── storage/             # Indexer, models, diff engine, templates
├── templates/               # Knowledge/memory/artifact templates
├── skills/                  # Harnext skill manifests
├── knowledge/               # Live knowledge store (index.json + *.md)
├── systemd/                 # systemd service + timer units
└── tests/                   # Unit tests
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```

## License

MIT
