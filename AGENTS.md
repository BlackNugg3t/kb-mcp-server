# AGENTS.md — GymBoost Knowledge Base

## Agent Creation Template & Integration Guidelines

This document is the single source of truth for adding new scanner agents, skills, or services to the KB MCP Server. Follow these rules strictly.

---

## Quickstart: Adding a New Service Scanner

### Step 1: Create the scanner class

Copy this template into `src/agents/{service_name}_scanner.py`:

```python
"""
{ServiceName} Scanner Agent

Scans {service_description} for project-relevant information.
Extracts {knowledge|memory|artifact} items from the findings.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import ServiceConfig
from ..storage.models import (
    BaseItem,
    Confidence,
    ItemStatus,
    ItemType,
    KnowledgeItem,   # or MemoryItem, ArtifactItem
    ScanResult,
    Source,
)
from .base import BaseScannerAgent

logger = logging.getLogger(__name__)


class {ServiceName}ScannerAgent(BaseScannerAgent):
    """Read-only scanner for {ServiceName} via MCP."""

    # REQUIRED: Set the source enum value
    source = Source.{SOURCE_ENUM_VALUE}

    def __init__(self, service_config: ServiceConfig, skill_path: str | None = None):
        super().__init__(service_config, skill_path)
        # Extract service-specific config fields here
        self.{custom_field} = service_config.{custom_field}

    # ── REQUIRED: implement scan() ──────────────────────────────────────

    def scan(self) -> ScanResult:
        return self._safe_scan(self._do_scan)

    def _do_scan(self) -> ScanResult:
        """Execute the full scan."""
        started_at = datetime.now(timezone.utc)
        all_items: list[BaseItem] = []
        all_snippets: list[str] = []
        total_scanned = 0

        agent = self._init_agent()

        # TODO: Use agent.run() with MCP tools to fetch data
        # Example:
        # result = agent.run("List all recent items from {service}")
        # Parse the result and extract items

        return self._make_scan_result(
            items=all_items,
            raw_snippets=all_snippets,
            started_at=started_at,
            items_scanned=total_scanned,
        )

    # ── REQUIRED: implement _extract_items() ────────────────────────────

    def _extract_items(self, raw_findings: list[dict[str, Any]]) -> list[BaseItem]:
        """Extract and classify items from raw findings."""
        items: list[BaseItem] = []

        for finding in raw_findings:
            item = KnowledgeItem(  # or MemoryItem / ArtifactItem
                id=f"{SOURCE_PREFIX}-{finding['key']}",
                source=self.source,
                source_id=finding.get("id", "unknown"),
                source_url=finding.get("url", ""),
                title=finding.get("title", "Untitled")[:300],
                summary=finding.get("summary", "")[:300],
                details=finding.get("content", ""),
                tags=self._infer_tags(finding),
                confidence=Confidence.HIGH,
                status=ItemStatus.ACTIVE,
                authors=finding.get("authors", []),
                context=f"Source: {finding.get('context', '')}",
                references=finding.get("url", ""),
            )
            items.append(item)

        return items

    def _infer_tags(self, finding: dict[str, Any]) -> list[str]:
        """Infer tags from finding content. Use ONLY taxonomy tags."""
        tags: list[str] = ["enhancement"]  # default
        content = finding.get("content", "").lower()
        # TODO: Add heuristic tag inference
        return tags
```

### Step 2: Register the scanner in the coordinator

In `src/coordinator.py`, add to the `_get_scanner` method's `scanner_map`:

```python
scanner_map = {
    "github": GitHubScannerAgent,
    "notion": NotionScannerAgent,
    "discord": DiscordScannerAgent,
    "telegram": TelegramScannerAgent,
    "{service_name}": {ServiceName}ScannerAgent,  # ← ADD THIS
}
```

### Step 3: Add a Source enum value

In `src/storage/models.py`, add to the `Source` enum:

```python
class Source(str, Enum):
    GITHUB = "github"
    NOTION = "notion"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    {SERVICE_NAME} = "{service_name}"  # ← ADD THIS
    MANUAL = "manual"
```

### Step 4: Create a skill manifest

Create `skills/scan-{service_name}/skill.md`:

```markdown
---
name: scan-{service_name}
description: Scan {ServiceName} for project-relevant information.
when_to_use: When the coordinator triggers a {ServiceName} scan cycle.
tools:
  - read
  - mcp
mcp_servers:
  - {service_name}
---

# Scan {ServiceName}

You are scanning {ServiceName} for the GymBoost knowledge base.
Your job is to find NEW or UPDATED content since the last scan.

## What to scan
...

## How to extract
...

## Output format
Return structured findings. READ ONLY — never modify {ServiceName} content.
```

### Step 5: Add to config.json services section

```json
"{service_name}": {
  "enabled": true,
  "priority": 5,
  "check_interval_minutes": 60,
  "description": "...",
  "mcp_server": {
    "command": "npx",
    "args": ["-y", "@scope/{service_name}-mcp-server"],
    "env": { "{SERVICE}_TOKEN": "${SERVICE_TOKEN}" },
    "mode": "proxy",
    "allow": ["tool1", "tool2"]
  },
  ...
}
```

---

## Mandatory Rules for All Agents

### 1. READ-ONLY — No Exceptions
Every scanner agent must use `tools=["read", "skill", "mcp"]`. Never include `"write"`, `"edit"`, or `"bash"` in scanner tool lists.

### 2. Source Origin Tag
Every persisted item MUST include an automatic `source:{service_name}` tag (e.g., `source:github`, `source:notion`). This is enforced by the coordinator's `_persist_item` method — not by individual scanners.

### 3. Taxonomy-Only Tags
Tags must come from the taxonomy in `config.json`. The validator rejects unknown tags. If you need new tags, add them to the taxonomy first.

### 4. Structured ScanResult Always
Every `scan()` must return a `ScanResult` with:
- `source` set to the correct `Source` enum
- `started_at` and `completed_at` timestamps
- `items_scanned` count
- `new_items` list (even if empty)
- `raw_snippets` for audit trail
- `error` string if scan failed

### 5. ID Convention
Follow the naming pattern: `{source_abbrev}-{type}-{identifier}`

| Source | Prefix | Example |
|--------|--------|---------|
| GitHub | `gh` | `gh-issue-42`, `gh-pr-100` |
| Notion | `nt` | `nt-page-abc12345` |
| Discord | `dc` | `dc-general-12345678` |
| Telegram | `tg` | `tg-dev-42` |
| New service | 2-4 char abbrev | `{abbr}-{type}-{id}` |

### 6. Error Resilience
- Never crash on a single item failure
- Log errors and continue processing remaining items
- Return partial results when possible
- Set `error` field in ScanResult for the coordinator to report

### 7. Test Coverage
Every new scanner needs:
- `test_extract_items` — verify `_extract_items` produces correct items
- `test_tag_inference` — verify tags come from taxonomy
- `test_disabled_scanner` — verify disabled flag is respected

---

## Skill Manifest Template

```markdown
---
name: {skill-name}
description: {one-line description}
when_to_use: {when the coordinator should invoke this skill}
tools:
  - read
  - mcp
mcp_servers:
  - {service_name}
---

# {Title}

## What to scan
...

## How to extract
...

## Output format
...
```

---

## Configuration Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | yes | `true` | Enable/disable this service |
| `priority` | int | yes | `5` | 1-10, higher = scanned first |
| `check_interval_minutes` | int | yes | `60` | Minimum minutes between scans |
| `description` | string | no | `""` | Human-readable description |
| `mcp_server.command` | string | yes | — | MCP server executable |
| `mcp_server.args` | list | yes | — | CLI arguments |
| `mcp_server.env` | dict | no | `{}` | Environment variables |
| `mcp_server.mode` | string | no | `"proxy"` | `proxy` or `direct` |
| `mcp_server.allow` | list | no | `[]` | Allowed MCP tools |

---

## Checklist: Adding a New Service

- [ ] `Source` enum value added to `src/storage/models.py`
- [ ] Scanner class created in `src/agents/{name}_scanner.py`
- [ ] Scanner extends `BaseScannerAgent`
- [ ] `source` class attribute set
- [ ] `scan()` method implemented
- [ ] `_extract_items()` method implemented
- [ ] Registered in `src/coordinator.py` scanner_map
- [ ] Skill manifest in `skills/scan-{name}/skill.md`
- [ ] Config entry in `config.json` with `priority` and `check_interval_minutes`
- [ ] MCP server tools allow-listed
- [ ] Unit tests in `tests/test_scanners.py`
- [ ] `.env.example` updated with new token
