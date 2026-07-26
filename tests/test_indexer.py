"""
Tests for the Knowledge Base Indexer.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.storage.indexer import Indexer
from src.storage.models import (
    IndexEntry,
    ItemType,
    KnowledgeItem,
    MemoryItem,
    Source,
)


class TestIndexerBasePathResolution:
    """
    Regression test: Indexer.base_path must be resolved to absolute at
    construction time. Previously it stayed relative (e.g. "./knowledge",
    as used by the real config.json), while make_file_path() resolves its
    own output — so coordinator._persist_item()'s
    file_path.relative_to(indexer.base_path) raised ValueError for every
    single item on a real run, even though scanning/diffing worked fine.
    """

    def test_make_file_path_relative_to_relative_base_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        indexer = Indexer(base_path="./knowledge")

        file_path = indexer.make_file_path("gh-issue-1", ItemType.KNOWLEDGE)

        # This is exactly what coordinator._persist_item() does after
        # make_file_path() — must not raise ValueError.
        relative = file_path.relative_to(indexer.base_path)
        assert relative == Path("knowledge/gh-issue-1.md")

    def test_base_path_is_absolute(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        indexer = Indexer(base_path="./knowledge")
        assert indexer.base_path.is_absolute()


class TestIndexer:
    """Tests for the Indexer class."""

    def test_create_new_index(self):
        """Indexer should create a new empty index when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(base_path=tmpdir, index_file="index.json")
            idx = indexer.load()

            assert idx.version == "1.0.0"
            assert len(idx.entries) == 0
            assert len(idx.tags) == 0

    def test_save_and_load(self):
        """Indexer should save and reload the index correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(base_path=tmpdir, index_file="index.json")

            entry = IndexEntry(
                id="gh-issue-42",
                type=ItemType.KNOWLEDGE,
                source=Source.GITHUB,
                source_id="repo#42",
                path="knowledge/gh-issue-42.md",
                title="Test Issue",
                tags=["bug", "security"],
            )

            indexer.add_or_update(entry)
            indexer.save()

            # Reload
            indexer2 = Indexer(base_path=tmpdir, index_file="index.json")
            idx2 = indexer2.load()

            assert len(idx2.entries) == 1
            assert idx2.entries[0].id == "gh-issue-42"
            assert idx2.entries[0].title == "Test Issue"
            assert "bug" in idx2.tags
            assert "security" in idx2.tags

    def test_search(self):
        """Index search should find entries by title or tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(base_path=tmpdir, index_file="index.json")

            entries = [
                IndexEntry(
                    id="gh-issue-1",
                    type=ItemType.KNOWLEDGE,
                    source=Source.GITHUB,
                    source_id="repo#1",
                    path="k/gh-issue-1.md",
                    title="Fix login crash",
                    tags=["bug", "auth"],
                ),
                IndexEntry(
                    id="gh-issue-2",
                    type=ItemType.KNOWLEDGE,
                    source=Source.GITHUB,
                    source_id="repo#2",
                    path="k/gh-issue-2.md",
                    title="Add dark mode",
                    tags=["enhancement", "ui"],
                ),
            ]

            for entry in entries:
                indexer.add_or_update(entry)

            # Search by title
            results = indexer.search("login")
            assert len(results) == 1
            assert results[0].id == "gh-issue-1"

            # Search by tag
            results = indexer.search("auth")
            assert len(results) == 1

            # Search with no match
            results = indexer.search("nonexistent")
            assert len(results) == 0

    def test_search_by_source_tag(self):
        """Search should find items by source:{name} origin tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(base_path=tmpdir, index_file="index.json")

            entries = [
                IndexEntry(
                    id="gh-issue-1",
                    type=ItemType.KNOWLEDGE,
                    source=Source.GITHUB,
                    source_id="repo#1",
                    path="k/gh-issue-1.md",
                    title="Bug from GitHub",
                    tags=["bug", "source:github"],
                ),
                IndexEntry(
                    id="nt-page-1",
                    type=ItemType.KNOWLEDGE,
                    source=Source.NOTION,
                    source_id="page-1",
                    path="k/nt-page-1.md",
                    title="Doc from Notion",
                    tags=["documentation", "source:notion"],
                ),
            ]

            for entry in entries:
                indexer.add_or_update(entry)

            # Search by source tag
            results = indexer.search("source:github")
            assert len(results) == 1
            assert results[0].id == "gh-issue-1"

            results = indexer.search("source:notion")
            assert len(results) == 1
            assert results[0].id == "nt-page-1"

    def test_make_entry_id(self):
        """Entry ID generation should follow conventions."""
        assert Indexer.make_entry_id(Source.GITHUB, "issue/106") == "gh-issue-106"
        assert Indexer.make_entry_id(Source.NOTION, "page/abc12345") == "nt-page-abc12345"
        assert Indexer.make_entry_id(Source.DISCORD, "msg/789") == "dc-msg-789"
        assert Indexer.make_entry_id(Source.TELEGRAM, "msg/42") == "tg-msg-42"

    def test_add_and_remove_entry(self):
        """Should add and remove entries correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = Indexer(base_path=tmpdir, index_file="index.json")

            entry = IndexEntry(
                id="test-1",
                type=ItemType.KNOWLEDGE,
                source=Source.MANUAL,
                source_id="manual-1",
                path="k/test-1.md",
                title="Test Entry",
                tags=["test"],
            )

            indexer.add_or_update(entry)
            assert indexer.total_entries == 1

            indexer.remove("test-1")
            assert indexer.total_entries == 0


class TestConfigPriorityIntervals:
    """Tests for per-source priority and check_interval_minutes."""

    def test_config_parses_priority(self):
        """ServiceConfig should parse priority and check_interval_minutes."""
        from src.config import ServiceConfig, MCPServiceDef

        svc = ServiceConfig(
            enabled=True,
            priority=10,
            check_interval_minutes=15,
            mcp_server=MCPServiceDef(command="npx", args=["test"]),
        )

        assert svc.priority == 10
        assert svc.check_interval_minutes == 15

    def test_config_default_priority(self):
        """ServiceConfig should default to priority=5."""
        from src.config import ServiceConfig, MCPServiceDef

        svc = ServiceConfig(
            mcp_server=MCPServiceDef(command="npx", args=["test"]),
        )

        assert svc.priority == 5
        assert svc.check_interval_minutes == 60


class TestSourceOriginTag:
    """Tests for automatic source origin tagging."""

    def test_knowledge_item_gets_source_tag(self):
        """Persisted items should get automatic source:name tag."""
        from src.coordinator import Coordinator

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal config
            config_data = {
                "name": "test",
                "version": "1.0",
                "services": {
                    "github": {
                        "enabled": False,
                        "priority": 10,
                        "check_interval_minutes": 15,
                        "mcp_server": {"command": "echo", "args": []},
                    }
                },
                "storage": {"base_path": tmpdir},
                "tags": {"taxonomy": ["bug", "enhancement"]},
                "llm": {"provider": "none"},
                "mcp_server": {"mode": "stdio"},
            }
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config_data))

            coordinator = Coordinator(str(config_path))

            # Create an item and persist it
            item = KnowledgeItem(
                id="gh-test-1",
                source=Source.GITHUB,
                source_id="test#1",
                title="Test Item",
                summary="Testing source tags",
                tags=["bug"],
            )

            coordinator._persist_item(item)

            # Check the index entry has the source tag
            entry = coordinator.indexer.get_entry("gh-test-1")
            assert entry is not None
            assert "source:github" in entry.tags
            assert "bug" in entry.tags

            # Check the file exists and has the source tag in frontmatter
            file_path = coordinator.indexer.make_file_path("gh-test-1", ItemType.KNOWLEDGE)
            assert file_path.exists()
            content = file_path.read_text()
            assert "source: github" in content
