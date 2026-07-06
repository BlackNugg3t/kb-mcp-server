"""
Change Detection & Deduplication Engine

Compares incoming scan items against the existing knowledge base,
detects new/updated/unchanged items, and handles near-duplicate detection.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Optional

from .models import (
    BaseItem,
    Confidence,
    DiffResult,
    IndexEntry,
    ItemType,
    KnowledgeItem,
    MasterIndex,
    Source,
)

logger = logging.getLogger(__name__)


# ── Similarity threshold for near-duplicate detection ───────────────────────

SIMILARITY_THRESHOLD = 0.85  # 85% similarity = potential duplicate


# ── Diff Engine ──────────────────────────────────────────────────────────────


class DiffEngine:
    """Handles change detection between new scan data and the existing index."""

    def __init__(self, index: MasterIndex):
        self.index = index

    def analyze(
        self,
        source: Source,
        incoming_items: list[BaseItem],
    ) -> DiffResult:
        """
        Analyze incoming items against the existing index.

        Returns a DiffResult categorizing items as new, updated, unchanged,
        removed, or duplicate.

        Args:
            source: The data source being analyzed
            incoming_items: Items extracted from the latest scan

        Returns:
            DiffResult with categorized items
        """
        result = DiffResult(source=source)

        # Build a set of existing IDs for this source
        existing_by_id: dict[str, IndexEntry] = {}
        for entry in self.index.entries:
            if entry.source == source:
                existing_by_id[entry.id] = entry

        incoming_ids: set[str] = set()

        for item in incoming_items:
            incoming_ids.add(item.id)
            existing_entry = existing_by_id.get(item.id)

            if existing_entry is None:
                # New item — check for near-duplicates
                if self._is_duplicate(item, source):
                    result.duplicates_skipped += 1
                    logger.debug("Skipping near-duplicate: %s", item.id)
                else:
                    result.new.append(item)
                    logger.info("New item: %s", item.id)
            else:
                # Existing item — check if content changed
                new_hash = self._hash_item(item)
                if new_hash != existing_entry.content_hash:
                    result.updated.append(item)
                    logger.info("Updated item: %s", item.id)
                else:
                    result.unchanged.append(item)

        # Detect removed items (in index but not in incoming)
        for entry_id in existing_by_id:
            if entry_id not in incoming_ids:
                result.removed.append(entry_id)
                logger.info("Removed from source: %s", entry_id)

        return result

    def _is_duplicate(self, item: BaseItem, source: Source) -> bool:
        """
        Check if an incoming item is a near-duplicate of an existing item.

        Uses content similarity comparison against existing items from the same source.
        """
        # Get existing items from the same source
        existing_items = [
            e for e in self.index.entries if e.source == source
        ]

        for existing in existing_items:
            # Skip if same ID (handled by the caller)
            if existing.id == item.id:
                continue

            # Compare titles for high similarity
            if isinstance(item, KnowledgeItem):
                title_sim = SequenceMatcher(None, item.title.lower(), existing.title.lower()).ratio()
                if title_sim > SIMILARITY_THRESHOLD:
                    # Also check summary similarity
                    summary = getattr(item, "summary", "")
                    # For a full check, we'd need to load the existing file
                    if title_sim > 0.95:  # Very high title similarity → likely duplicate
                        return True

        return False

    @staticmethod
    def _hash_item(item: BaseItem) -> str:
        """Compute a hash of an item's content for change detection."""
        import hashlib
        import json

        # Use the model dump as canonical representation
        data = item.model_dump(mode="json", exclude={"created", "updated"})
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_text_similarity(text1: str, text2: str) -> float:
        """
        Compute similarity ratio between two text strings.

        Returns a float between 0.0 (completely different) and 1.0 (identical).
        """
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    @staticmethod
    def is_stale(item: BaseItem, max_age_days: int = 90) -> bool:
        """
        Check if an item might be stale based on its age.
        Items older than max_age_days without updates are candidate for review.
        """
        from datetime import datetime, timezone

        age = datetime.now(timezone.utc) - item.updated
        return age.days > max_age_days


def compute_item_hash(content: str) -> str:
    """Compute SHA-256 hash of rendered content string."""
    import hashlib
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
