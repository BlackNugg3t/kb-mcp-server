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
