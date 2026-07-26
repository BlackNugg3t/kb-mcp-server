"""
Tests for src.harnext_bootstrap: the idempotent writers that register this
project's MCP servers and (optionally) a local "ollama" provider base URL
with harnext's own config files.

The autouse isolated_harnext_home fixture in tests/conftest.py already
points HARNEXT_HOME/HARNEXT_AGENT_DIR at a per-test tmp dir, so these tests
never touch the real ~/.harnext.
"""

import json

from src.config import KBConfig, MCPServiceDef, ServiceConfig
from src.harnext_bootstrap import (
    _agent_dir,
    _project_mcp_config_path,
    write_ollama_auth,
    write_project_mcp_config,
)


def make_config(**services: ServiceConfig) -> KBConfig:
    return KBConfig(services=services)


class TestWriteProjectMcpConfig:
    def test_writes_command_based_server(self, tmp_path):
        config = make_config(
            github=ServiceConfig(
                mcp_server=MCPServiceDef(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-github"],
                    env={"GITHUB_PERSONAL_ACCESS_TOKEN": "x"},
                    allow=["list_issues"],
                )
            )
        )
        cwd = tmp_path / "repo"
        cwd.mkdir()

        path = write_project_mcp_config(config, cwd)

        assert path == _project_mcp_config_path(cwd)
        data = json.loads(path.read_text())
        assert data["mcpServers"]["github"]["command"] == "npx"
        assert data["mcpServers"]["github"]["directTools"] == ["list_issues"]

    def test_skips_services_with_no_command_or_url(self, tmp_path):
        config = make_config(github=ServiceConfig(mcp_server=MCPServiceDef()))
        cwd = tmp_path / "repo"
        cwd.mkdir()

        path = write_project_mcp_config(config, cwd)
        data = json.loads(path.read_text())
        assert data["mcpServers"] == {}

    def test_idempotent_second_call_is_noop(self, tmp_path):
        config = make_config(
            github=ServiceConfig(mcp_server=MCPServiceDef(command="npx", args=["-y", "pkg"]))
        )
        cwd = tmp_path / "repo"
        cwd.mkdir()

        path = write_project_mcp_config(config, cwd)
        mtime_1 = path.stat().st_mtime_ns
        write_project_mcp_config(config, cwd)
        mtime_2 = path.stat().st_mtime_ns

        assert mtime_1 == mtime_2  # not rewritten

    def test_preserves_hand_edited_settings(self, tmp_path):
        config = make_config(
            github=ServiceConfig(mcp_server=MCPServiceDef(command="npx", args=[]))
        )
        cwd = tmp_path / "repo"
        cwd.mkdir()
        path = _project_mcp_config_path(cwd)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mcpServers": {}, "settings": {"toolPrefix": "short"}}))

        write_project_mcp_config(config, cwd)

        data = json.loads(path.read_text())
        assert data["settings"] == {"toolPrefix": "short"}
        assert "github" in data["mcpServers"]


class TestWriteOllamaAuth:
    def test_writes_base_url(self):
        path = write_ollama_auth("http://127.0.0.1:9999")
        assert path == _agent_dir() / "auth.json"
        data = json.loads(path.read_text())
        assert data["ollama"]["baseUrl"] == "http://127.0.0.1:9999"

    def test_merges_without_clobbering_other_providers(self):
        path = _agent_dir() / "auth.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"anthropic": {"key": "sk-abc"}}))

        write_ollama_auth("http://127.0.0.1:9999")

        data = json.loads(path.read_text())
        assert data["anthropic"]["key"] == "sk-abc"
        assert data["ollama"]["baseUrl"] == "http://127.0.0.1:9999"

    def test_idempotent_second_call_is_noop(self):
        write_ollama_auth("http://127.0.0.1:9999")
        path = _agent_dir() / "auth.json"
        mtime_1 = path.stat().st_mtime_ns
        write_ollama_auth("http://127.0.0.1:9999")
        mtime_2 = path.stat().st_mtime_ns
        assert mtime_1 == mtime_2
