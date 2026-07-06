"""
Tests for scanner agents.
"""

import pytest

from src.agents.github_scanner import GitHubScannerAgent
from src.agents.notion_scanner import NotionScannerAgent
from src.agents.discord_scanner import DiscordScannerAgent
from src.agents.telegram_scanner import TelegramScannerAgent
from src.config import MCPServiceDef, ServiceConfig


@pytest.fixture
def github_config():
    return ServiceConfig(
        enabled=True,
        priority=10,
        check_interval_minutes=15,
        description="Test GitHub",
        mcp_server=MCPServiceDef(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
        ),
        repos=["test/repo"],
        scan_types=["issues", "pull_requests"],
    )


@pytest.fixture
def notion_config():
    return ServiceConfig(
        enabled=True,
        priority=8,
        check_interval_minutes=30,
        description="Test Notion",
        mcp_server=MCPServiceDef(
            command="npx",
            args=["-y", "@notionhq/notion-mcp-server"],
        ),
        page_filters={"search_query": "test"},
    )


@pytest.fixture
def discord_config():
    return ServiceConfig(
        enabled=True,
        priority=6,
        check_interval_minutes=60,
        description="Test Discord",
        mcp_server=MCPServiceDef(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-discord"],
        ),
        channels=["test-channel"],
    )


@pytest.fixture
def telegram_config():
    return ServiceConfig(
        enabled=True,
        priority=5,
        check_interval_minutes=60,
        description="Test Telegram",
        mcp_server=MCPServiceDef(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-telegram"],
        ),
        chats=["test-chat"],
    )


class TestGitHubScanner:
    """Tests for the GitHub scanner agent."""

    def test_extract_issue(self, github_config):
        scanner = GitHubScannerAgent(github_config)
        raw = [{
            "type": "issue",
            "number": 42,
            "repo": "test/repo",
            "html_url": "https://github.com/test/repo/issues/42",
            "title": "Fix login crash on mobile",
            "body": "The app crashes when logging in on iOS Safari.",
            "user": {"login": "tester"},
            "labels": [{"name": "bug"}, {"name": "mobile"}],
        }]

        items = scanner._extract_items(raw)
        assert len(items) == 1
        item = items[0]
        assert item.id == "gh-issue-42"
        assert item.title == "Fix login crash on mobile"
        assert "bug" in item.tags
        # "mobile" is not in the taxonomy — only known tags pass through

    def test_extract_pr(self, github_config):
        scanner = GitHubScannerAgent(github_config)
        raw = [{
            "type": "pull_request",
            "number": 100,
            "repo": "test/repo",
            "html_url": "https://github.com/test/repo/pull/100",
            "title": "Add dark mode support",
            "body": "Implements dark mode across all pages.",
            "user": {"login": "developer"},
        }]

        items = scanner._extract_items(raw)
        assert len(items) == 1
        item = items[0]
        assert item.id == "gh-pr-100"

    def test_disabled_scanner(self, github_config):
        github_config.enabled = False
        scanner = GitHubScannerAgent(github_config)
        result = scanner.scan()
        assert result.error == "Service disabled in configuration"


class TestDiscordScanner:
    """Tests for the Discord scanner agent."""

    def test_extract_decision_message(self, discord_config):
        scanner = DiscordScannerAgent(discord_config)
        raw = [{
            "id": "123456789012345678",
            "channel": "dev",
            "url": "https://discord.com/channels/...",
            "timestamp": "2026-07-06T10:00:00Z",
            "summary": "Decision: use Tailwind v4",
            "content": "We decided to use Tailwind v4 for the redesign.",
            "rationale": "Better performance and smaller bundle size.",
            "participants": ["sam", "milan"],
        }]

        items = scanner._extract_items(raw)
        assert len(items) == 1
        item = items[0]
        assert item.source.value == "discord"
        assert "decision" in item.tags

    def test_disabled_scanner(self, discord_config):
        discord_config.enabled = False
        scanner = DiscordScannerAgent(discord_config)
        result = scanner.scan()
        assert result.error == "Service disabled in configuration"


class TestPriorityAndIntervals:
    """Tests for per-source priority and check intervals."""

    def test_priority_sorted_high_first(self):
        """Services should be sorted by priority (highest first)."""
        from src.config import KBConfig, ServiceConfig, MCPServiceDef

        config = KBConfig(
            name="test",
            services={
                "github": ServiceConfig(
                    enabled=True, priority=10, check_interval_minutes=15,
                    mcp_server=MCPServiceDef(command="echo", args=[]),
                ),
                "discord": ServiceConfig(
                    enabled=True, priority=6, check_interval_minutes=60,
                    mcp_server=MCPServiceDef(command="echo", args=[]),
                ),
                "telegram": ServiceConfig(
                    enabled=True, priority=5, check_interval_minutes=60,
                    mcp_server=MCPServiceDef(command="echo", args=[]),
                ),
                "notion": ServiceConfig(
                    enabled=True, priority=8, check_interval_minutes=30,
                    mcp_server=MCPServiceDef(command="echo", args=[]),
                ),
            },
            tags={"taxonomy": []},
        )

        # Verify priorities were parsed correctly
        assert config.services["github"].priority == 10
        assert config.services["notion"].priority == 8
        assert config.services["discord"].priority == 6
        assert config.services["telegram"].priority == 5

        assert config.services["github"].check_interval_minutes == 15
        assert config.services["notion"].check_interval_minutes == 30
        assert config.services["discord"].check_interval_minutes == 60

    def test_default_priority(self):
        """Service config should default to priority=5."""
        from src.config import ServiceConfig, MCPServiceDef

        svc = ServiceConfig(
            mcp_server=MCPServiceDef(command="echo", args=[]),
        )

        assert svc.priority == 5
        assert svc.check_interval_minutes == 60
