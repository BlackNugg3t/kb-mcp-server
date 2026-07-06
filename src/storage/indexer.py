"""
Knowledge Base Indexer

Manages the master index (index.json), providing CRUD operations
for entries and maintaining tag/cross-reference indices.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    IndexEntry,
    ItemType,
    MasterIndex,
    ScanStats,
    Source,
)

logger = logging.getLogger(__name__)


class Indexer:
    """Manages the master knowledge base index file."""

    def __init__(self, base_path: str | Path = "./knowledge", index_file: str = "index.json"):
        self.base_path = Path(base_path)
        self.index_path = self.base_path / index_file
        self._index: Optional[MasterIndex] = None

    @property
    def index(self) -> MasterIndex:
        """Get the current index, loading from disk if needed."""
        if self._index is None:
            self._index = self.load()
        return self._index

    def load(self) -> MasterIndex:
        """Load the master index from disk. Returns a new empty index if file doesn't exist."""
        if not self.index_path.exists():
            logger.info("Index file not found at %s, creating new index", self.index_path)
            return MasterIndex()

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return MasterIndex(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Failed to parse index file: %s. Creating new index.", e)
            return MasterIndex()

    def save(self) -> None:
        """Persist the current index to disk."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        data = self.index.model_dump(mode="json")
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        logger.info("Index saved: %d entries, %d tags", self.index.total_entries, self.index.total_tags)

    def reload(self) -> MasterIndex:
        """Force reload from disk."""
        self._index = None
        return self.index

    def get_entry(self, entry_id: str) -> Optional[IndexEntry]:
        """Get an entry by its ID."""
        return self.index.get_by_id(entry_id)

    def entry_exists(self, entry_id: str) -> bool:
        """Check if an entry with the given ID exists."""
        return self.index.get_by_id(entry_id) is not None

    def add_or_update(self, entry: IndexEntry) -> None:
        """Add a new entry or update an existing one."""
        self.index.add_entry(entry)
        logger.debug("Index entry %s: %s", "updated" if self.entry_exists(entry.id) else "added", entry.id)

    def remove(self, entry_id: str) -> bool:
        """Remove an entry from the index."""
        return self.index.remove_entry(entry_id)

    def get_by_tag(self, tag: str) -> list[IndexEntry]:
        """Get all entries with a given tag."""
        return self.index.get_by_tag(tag)

    def get_by_source(self, source: Source) -> list[IndexEntry]:
        """Get all entries from a given source."""
        return self.index.get_by_source(source)

    def get_by_type(self, item_type: ItemType) -> list[IndexEntry]:
        """Get all entries of a given type."""
        return self.index.get_by_type(item_type)

    def search(self, query: str) -> list[IndexEntry]:
        """Search entries by title and tags."""
        return self.index.search(query)

    def update_scan_stats(self, source: Source, stats: ScanStats) -> None:
        """Update scan statistics for a given source."""
        self.index.scan_stats[source.value] = stats

    def get_scan_stats(self, source: Source) -> Optional[ScanStats]:
        """Get scan statistics for a given source."""
        return self.index.scan_stats.get(source.value)

    def update_last_full_scan(self, timestamp: Optional[datetime] = None) -> None:
        """Update the timestamp of the last full scan."""
        self.index.last_full_scan = timestamp or datetime.now(timezone.utc)

    def add_cross_ref(self, from_id: str, to_id: str) -> None:
        """Add a cross-reference between two entries."""
        if from_id not in self.index.cross_refs:
            self.index.cross_refs[from_id] = []
        if to_id not in self.index.cross_refs[from_id]:
            self.index.cross_refs[from_id].append(to_id)

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute SHA-256 hash of content for change detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def make_entry_id(source: Source, source_identifier: str) -> str:
        """
        Generate a standard entry ID from source and identifier.

        Examples:
            github + "issue/106" → "gh-issue-106"
            notion + "page/abc12345" → "nt-page-abc12345"
            discord + "msg/789" → "dc-msg-789"
        """
        source_prefix = {
            Source.GITHUB: "gh",
            Source.NOTION: "nt",
            Source.DISCORD: "dc",
            Source.TELEGRAM: "tg",
            Source.MANUAL: "kb",
        }
        prefix = source_prefix.get(source, "unknown")
        # Convert slashes and special chars to dashes
        safe_id = source_identifier.replace("/", "-").replace(" ", "-").lower()
        # Take last 40 chars max to avoid overly long IDs
        if len(safe_id) > 40:
            safe_id = safe_id[-40:]
        return f"{prefix}-{safe_id}"

    def make_file_path(self, entry_id: str, item_type: ItemType) -> Path:
        """
        Generate the filesystem path for a knowledge base file.

        Args:
            entry_id: The entry's unique ID
            item_type: The type of item (knowledge/memory/artifact)

        Returns:
            Relative path from the knowledge base root
        """
        dir_name = f"{item_type.value}s"  # knowledge → knowledges, memory → memories
        if item_type == ItemType.KNOWLEDGE:
            dir_name = "knowledge"
        return self.base_path / dir_name / f"{entry_id}.md"

    @property
    def total_entries(self) -> int:
        return self.index.total_entries

    @property
    def total_tags(self) -> int:
        return self.index.total_tags

    @property
    def all_tags(self) -> list[str]:
        return self.index.all_tags
