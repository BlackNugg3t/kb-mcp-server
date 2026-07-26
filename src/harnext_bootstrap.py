"""
Harnext Bootstrap

Real harnext expects MCP servers pre-registered in its own project-scope
`mcp.json` (not passed inline per-query), and reads provider base URLs
(e.g. for a local/proxy "ollama" provider) from its own `auth.json`. This
module writes both from this project's existing `config.json`, so nothing
about `config.json`'s shape needs to change.

Both writers are idempotent — they only touch disk when content actually
differs, and never clobber other providers'/settings' entries.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .config import KBConfig

logger = logging.getLogger(__name__)

# Read-only KB query tools exposed to the chat agent (and, incidentally, to
# the scanners too — see the tool-visibility trade-off noted below).
# Deliberately excludes rescan_kb/reload_index/import_kb.
_KB_SELF_QUERY_TOOLS = ["search_kb", "get_knowledge", "list_tags", "list_sources", "get_kb_stats"]


def _harnext_home() -> Path:
    return Path(os.environ.get("HARNEXT_HOME", str(Path.home() / ".harnext")))


def _agent_dir() -> Path:
    return Path(os.environ.get("HARNEXT_AGENT_DIR", str(_harnext_home() / "agent")))


def _project_hash(cwd: Path) -> str:
    """Mirror harnext's own getProjectHash(): sha256(cwd).hexdigest()[:12]."""
    return hashlib.sha256(str(cwd).encode("utf-8")).hexdigest()[:12]


def _project_mcp_config_path(cwd: Path) -> Path:
    return _harnext_home() / "projects" / _project_hash(cwd) / "mcp.json"


def _write_json_if_changed(path: Path, data: dict[str, Any]) -> bool:
    """Write `data` as JSON to `path` only if it differs from what's already there."""
    new_content = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == new_content:
                return False
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_content, encoding="utf-8")
    return True


def write_project_mcp_config(
    config: KBConfig, cwd: Path | None = None, config_path: Path | str | None = None
) -> Path:
    """
    Register this project's per-service MCP servers (config.json's
    services.<name>.mcp_server blocks) into harnext's project-scope mcp.json,
    so scanner query() calls (setting_sources=["project"]) can reach them.

    If `config_path` is given, also registers a synthetic "kb-self" entry
    spawning this same server over stdio (`serve --transport stdio`), scoped
    via directTools to only the read-only query tools — this is what gives
    the chat agent (src/chat_agent.py) real tool-calling access to
    search_kb/get_knowledge/etc. Known trade-off: harnext's project mcp.json
    gives all-or-nothing tool visibility per query, so scanners will
    incidentally also see these KB tools (harmless, read-only), and the chat
    agent will incidentally also see the raw external service tools
    (mitigated there via HarnextAgentOptions.disallowed_tools).
    """
    cwd = Path(cwd or Path.cwd()).resolve()
    path = _project_mcp_config_path(cwd)

    mcp_servers: dict[str, Any] = {}
    for name, svc in config.services.items():
        mcp_def = svc.mcp_server
        if not (mcp_def.command or mcp_def.url):
            continue
        entry: dict[str, Any] = {}
        if mcp_def.command:
            entry["command"] = mcp_def.command
            entry["args"] = mcp_def.args
            if mcp_def.env:
                entry["env"] = mcp_def.env
        if mcp_def.url:
            entry["url"] = mcp_def.url
        if mcp_def.allow:
            entry["directTools"] = mcp_def.allow
        mcp_servers[name] = entry

    if config_path is not None:
        mcp_servers["kb-self"] = {
            "command": sys.executable,
            "args": [
                "-m", "src.main", "serve",
                "--config", str(Path(config_path).resolve()),
                "--transport", "stdio",
            ],
            "cwd": str(cwd),
            "directTools": list(_KB_SELF_QUERY_TOOLS),
        }

    data: dict[str, Any] = {"mcpServers": mcp_servers}

    # Preserve any hand-edited "settings" block already in the file.
    if path.exists():
        try:
            existing_settings = json.loads(path.read_text(encoding="utf-8")).get("settings")
            if existing_settings:
                data["settings"] = existing_settings
        except (json.JSONDecodeError, OSError):
            pass

    if _write_json_if_changed(path, data):
        logger.info("Wrote harnext project MCP config: %s (%d server(s))", path, len(mcp_servers))
    return path


def write_ollama_auth(base_url: str) -> Path:
    """
    Register a local/proxy OpenAI-compatible endpoint under harnext's "ollama"
    provider slot, so provider="ollama" queries hit it instead of the default
    localhost:11434. Merges into auth.json without touching other providers.
    """
    path = _agent_dir() / "auth.json"

    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}

    data.setdefault("ollama", {})
    data["ollama"]["baseUrl"] = base_url

    if _write_json_if_changed(path, data):
        try:
            path.chmod(0o600)
        except OSError:
            pass
        logger.info("Wrote harnext ollama auth config: %s -> baseUrl=%s", path, base_url)
    return path


def bootstrap(config: KBConfig, cwd: Path | None = None, config_path: Path | str | None = None) -> None:
    """Run both bootstrap steps once. Idempotent — safe to call on every startup."""
    write_project_mcp_config(config, cwd, config_path=config_path)
    if config.llm.provider == "ollama":
        write_ollama_auth(config.llm.ollama_base_url)
