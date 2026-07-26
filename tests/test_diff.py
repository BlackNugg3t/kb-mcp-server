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

    def test_near_duplicate_skipped(self):
        """A new item with a near-identical title to an existing entry should be skipped, not added as new."""
        entry = IndexEntry(
            id="gh-issue-1",
            type=ItemType.KNOWLEDGE,
            source=Source.GITHUB,
            source_id="repo#1",
            path="k/gh-issue-1.md",
            title="Login page crashes on submit",
            tags=["bug"],
        )
        index = MasterIndex(entries=[entry])
        diff = DiffEngine(index)

        near_dup = KnowledgeItem(
            id="gh-issue-2",  # different id, so it's a "new" candidate
            source=Source.GITHUB,
            source_id="repo#2",
            title="Login page crashes on submit",  # identical title -> similarity 1.0
            summary="Same bug reported again",
        )

        result = diff.analyze(Source.GITHUB, [near_dup])

        assert len(result.new) == 0
        assert result.duplicates_skipped == 1

    def test_dissimilar_title_not_duplicate(self):
        """A new item with a sufficiently different title should not be flagged as a duplicate."""
        entry = IndexEntry(
            id="gh-issue-1",
            type=ItemType.KNOWLEDGE,
            source=Source.GITHUB,
            source_id="repo#1",
            path="k/gh-issue-1.md",
            title="Login page crashes on submit",
            tags=["bug"],
        )
        index = MasterIndex(entries=[entry])
        diff = DiffEngine(index)

        distinct_item = KnowledgeItem(
            id="gh-issue-2",
            source=Source.GITHUB,
            source_id="repo#2",
            title="Add dark mode support",
            summary="Feature request for dark theme",
        )

        result = diff.analyze(Source.GITHUB, [distinct_item])

        assert len(result.new) == 1
        assert result.duplicates_skipped == 0
