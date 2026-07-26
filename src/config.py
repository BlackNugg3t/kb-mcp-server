"""
Configuration Loader

Loads and validates config.json, resolves environment variable placeholders,
and provides typed access to all configuration sections.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ── Config Models ───────────────────────────────────────────────────────────


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    fallback_model: str = ""
    max_turns: int = 20
    # Must be a real harnext PermissionMode: default/acceptEdits/plan/dontAsk/bypassPermissions.
    # "dontAsk" denies any tool not explicitly in allowed_tools (confirmed via harnext's
    # tool-policy.ts) — since we scope tool access at the MCP-server-registration level
    # (directTools/allow, see src/harnext_bootstrap.py) instead of allowed_tools, scanners
    # and the chat agent need "bypassPermissions" or every tool call is silently denied.
    permission_mode: str = "bypassPermissions"
    # Only used when provider == "ollama" — base URL for a local/proxy OpenAI-compatible
    # server registered under harnext's "ollama" provider slot (see src/harnext_bootstrap.py).
    ollama_base_url: str = "http://127.0.0.1:11434"


class MCPServerConfig(BaseModel):
    mode: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 9020
    description: str = ""
    auth_token: str = ""
    rate_limit_rescan_seconds: int = 300
    rate_limit_import_seconds: int = 300


class MCPServiceDef(BaseModel):
    """Definition of an MCP server for a connected service."""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    mode: str = "proxy"
    allow: list[str] = Field(default_factory=list)


class GitHubFilters(BaseModel):
    issues: dict[str, Any] = Field(default_factory=dict)
    pull_requests: dict[str, Any] = Field(default_factory=dict)
    commits: dict[str, Any] = Field(default_factory=dict)


class ServiceConfig(BaseModel):
    enabled: bool = True
    priority: int = 5
    check_interval_minutes: int = 60
    description: str = ""
    mcp_server: MCPServiceDef = Field(default_factory=MCPServiceDef)
    repos: list[str] = Field(default_factory=list)
    scan_types: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    databases: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    chats: list[str] = Field(default_factory=list)
    page_filters: dict[str, Any] = Field(default_factory=dict)
    message_filters: dict[str, Any] = Field(default_factory=dict)


class StorageConfig(BaseModel):
    base_path: str = "./knowledge"
    index_file: str = "index.json"
    memories_dir: str = "memories"
    knowledge_dir: str = "knowledge"
    artifacts_dir: str = "artifacts"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/kb-mcp-server.log"
    debug: bool = False
    activity_log_file: str = "logs/activity.jsonl"


class KBConfig(BaseModel):
    """Top-level configuration model."""
    name: str = "gymboost-knowledge-base"
    version: str = "1.0.0"
    description: str = ""
    scan_interval_minutes: int = 30
    scan_jitter_seconds: int = 60
    llm: LLMConfig = Field(default_factory=LLMConfig)
    mcp_server: MCPServerConfig = Field(default_factory=MCPServerConfig)
    services: dict[str, ServiceConfig] = Field(default_factory=dict)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    tags: dict[str, list[str]] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# ── Loader ───────────────────────────────────────────────────────────────────


_ENV_VAR_RE = re.compile(r"\$\{(\w+)\}")


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    return _ENV_VAR_RE.sub(replacer, value)


def _resolve_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve env vars in dict values."""
    result = {}
    for key, value in d.items():
        if isinstance(value, str):
            result[key] = _resolve_env(value)
        elif isinstance(value, dict):
            result[key] = _resolve_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _resolve_env(v) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
    return result


def load_config(config_path: str | Path = "config.json") -> KBConfig:
    """
    Load and validate the configuration from a JSON file.

    Args:
        config_path: Path to config.json

    Returns:
        Validated KBConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Remove $schema key if present (not part of our model)
    raw.pop("$schema", None)

    # Resolve environment variables
    raw = _resolve_dict(raw)

    return KBConfig(**raw)


def get_enabled_services(config: KBConfig) -> dict[str, ServiceConfig]:
    """Return only enabled services from the config."""
    return {name: svc for name, svc in config.services.items() if svc.enabled}


def get_validated_tags(config: KBConfig) -> list[str]:
    """Return the list of valid tags from the config taxonomy."""
    return config.tags.get("taxonomy", [])
