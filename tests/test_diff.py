"""
Tests for the Diff Engine.
"""

import tempfile
from pathlib import Path

import pytest

from src.storage.diff import DiffEngine
from src.storage.indexer import Indexer
from src.storage.models import (
    IndexEntry,
    ItemType,
    KnowledgeItem,
    MasterIndex,
    Source,
)


class TestDiffEngine:
    """Tests for the DiffEngine class."""

    def test_new_items_detected(self):
        """Diff engine should detect items not in the index as new."""
        index = MasterIndex()
        diff = DiffEngine(index)

        new_item = KnowledgeItem(
            id="gh-issue-1",
            source=Source.GITHUB,
            source_id="repo#1",
            title="New bug",
            summary="A new bug was found",
            tags=["bug"],
        )

        result = diff.analyze(Source.GITHUB, [new_item])

        assert len(result.new) == 1
        assert len(result.updated) == 0
        assert len(result.unchanged) == 0

    def test_unchanged_items_detected(self):
        """Diff engine should detect unchanged items."""
        entry = IndexEntry(
            id="gh-issue-1",
            type=ItemType.KNOWLEDGE,
            source=Source.GITHUB,
            source_id="repo#1",
            path="k/gh-issue-1.md",
            title="Existing bug",
            tags=["bug"],
            content_hash=DiffEngine._hash_item(
                KnowledgeItem(
                    id="gh-issue-1",
                    source=Source.GITHUB,
                    source_id="repo#1",
                    title="Existing bug",
                    summary="Same content",
                )
            ),
        )

        index = MasterIndex(entries=[entry])
        diff = DiffEngine(index)

        existing = KnowledgeItem(
            id="gh-issue-1",
            source=Source.GITHUB,
            source_id="repo#1",
            title="Existing bug",
            summary="Same content",  # Unchanged
        )

        result = diff.analyze(Source.GITHUB, [existing])

        assert len(result.new) == 0
        assert len(result.updated) == 0
        assert len(result.unchanged) == 1

    def test_updated_items_detected(self):
        """Diff engine should detect items with changed content."""
        entry = IndexEntry(
            id="gh-issue-1",
            type=ItemType.KNOWLEDGE,
            source=Source.GITHUB,
            source_id="repo#1",
            path="k/gh-issue-1.md",
            title="Existing bug",
            tags=["bug"],
            content_hash="old_hash",
        )

        index = MasterIndex(entries=[entry])
        diff = DiffEngine(index)

        updated = KnowledgeItem(
            id="gh-issue-1",
            source=Source.GITHUB,
            source_id="repo#1",
            title="Existing bug",
            summary="Updated content — now with more details",  # Changed
        )

        result = diff.analyze(Source.GITHUB, [updated])

        assert len(result.new) == 0
        assert len(result.updated) == 1
        assert len(result.unchanged) == 0

    def test_removed_items_detected(self):
        """Diff engine should detect items in index but not in scan."""
        entry = IndexEntry(
            id="gh-issue-1",
            type=ItemType.KNOWLEDGE,
            source=Source.GITHUB,
            source_id="repo#1",
            path="k/gh-issue-1.md",
            title="Deleted issue",
            tags=["bug"],
        )

        index = MasterIndex(entries=[entry])
        diff = DiffEngine(index)

        # No items from this source in the scan
        result = diff.analyze(Source.GITHUB, [])

        assert len(result.removed) == 1
        assert "gh-issue-1" in result.removed

    def test_text_similarity(self):
        """Text similarity computation should work correctly."""
        assert DiffEngine.compute_text_similarity("hello world", "hello world") == 1.0
        assert DiffEngine.compute_text_similarity("hello", "world") < 0.5
        assert DiffEngine.compute_text_similarity("fix login bug", "fix login crash") > 0.7
