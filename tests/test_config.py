"""
Tests for configuration loading and validation.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.config import (
    KBConfig,
    ServiceConfig,
    MCPServiceDef,
    _resolve_env,
    _resolve_dict,
    get_enabled_services,
    load_config,
)


class TestEnvResolution:
    """Tests for environment variable resolution."""

    def test_resolve_env(self):
        """Should replace ${VAR} with environment variable value."""
        os.environ["TEST_VAR"] = "secret123"
        assert _resolve_env("token=${TEST_VAR}") == "token=secret123"
        del os.environ["TEST_VAR"]

    def test_resolve_unset_var(self):
        """Should replace unset vars with empty string."""
        assert _resolve_env("token=${MISSING_VAR}") == "token="

    def test_resolve_dict_recursive(self):
        """Should recursively resolve env vars in nested dicts."""
        os.environ["GH_TOKEN"] = "ghp_abc"
        d = {
            "env": {"GITHUB_TOKEN": "${GH_TOKEN}"},
            "nested": {"deep": {"key": "val${GH_TOKEN}"}},
        }
        result = _resolve_dict(d)
        assert result["env"]["GITHUB_TOKEN"] == "ghp_abc"
        assert result["nested"]["deep"]["key"] == "valghp_abc"
        del os.environ["GH_TOKEN"]


class TestConfigLoading:
    """Tests for config.json loading."""

    def test_load_minimal_config(self):
        """Should load a minimal valid config."""
        config_data = {
            "name": "test-kb",
            "version": "1.0.0",
            "services": {},
            "storage": {"base_path": "/tmp/kb"},
            "tags": {"taxonomy": []},
            "llm": {"provider": "none"},
            "mcp_server": {"mode": "stdio"},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config_data))
            config = load_config(str(config_path))
            assert config.name == "test-kb"
            assert config.version == "1.0.0"

    def test_load_with_service_priority(self):
        """Should load service configs with priority and intervals."""
        config_data = {
            "name": "test-kb",
            "version": "1.0.0",
            "services": {
                "github": {
                    "enabled": True,
                    "priority": 10,
                    "check_interval_minutes": 15,
                    "mcp_server": {
                        "command": "npx",
                        "args": ["test"],
                    },
                },
                "notion": {
                    "enabled": True,
                    "priority": 8,
                    "check_interval_minutes": 30,
                    "mcp_server": {
                        "command": "npx",
                        "args": ["test"],
                    },
                },
            },
            "storage": {"base_path": "/tmp/kb"},
            "tags": {"taxonomy": ["bug", "enhancement"]},
            "llm": {"provider": "none"},
            "mcp_server": {"mode": "stdio"},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config_data))
            config = load_config(str(config_path))

            assert config.services["github"].priority == 10
            assert config.services["github"].check_interval_minutes == 15
            assert config.services["notion"].priority == 8
            assert config.services["notion"].check_interval_minutes == 30

    def test_enabled_services_filter(self):
        """get_enabled_services should return only enabled services."""
        config = KBConfig(
            name="test",
            services={
                "github": ServiceConfig(
                    enabled=True,
                    priority=10,
                    check_interval_minutes=15,
                    mcp_server=MCPServiceDef(command="echo", args=[]),
                ),
                "discord": ServiceConfig(
                    enabled=False,
                    priority=6,
                    mcp_server=MCPServiceDef(command="echo", args=[]),
                ),
            },
            tags={"taxonomy": []},
        )

        enabled = get_enabled_services(config)
        assert "github" in enabled
        assert "discord" not in enabled
        assert len(enabled) == 1

    def test_service_config_defaults(self):
        """ServiceConfig should have sensible defaults."""
        svc = ServiceConfig(
            mcp_server=MCPServiceDef(command="echo", args=[]),
        )
        assert svc.enabled is True
        assert svc.priority == 5
        assert svc.check_interval_minutes == 60

    def test_validate_mcp_server_def(self):
        """MCPServiceDef should validate correctly."""
        mcp = MCPServiceDef(
            command="npx",
            args=["-y", "server-package"],
            env={"TOKEN": "xxx"},
            allow=["tool1", "tool2"],
        )
        assert mcp.command == "npx"
        assert len(mcp.args) == 2
        assert mcp.env["TOKEN"] == "xxx"
        assert len(mcp.allow) == 2
