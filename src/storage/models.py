"""
Knowledge Base Data Models

Pydantic models for Knowledge, Memory, Artifact items and the Master Index.
These are the canonical data structures used throughout the system.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────


class ItemType(str, Enum):
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    ARTIFACT = "artifact"


class Source(str, Enum):
    GITHUB = "github"
    NOTION = "notion"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    MANUAL = "manual"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Importance(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Decay(str, Enum):
    PERMANENT = "permanent"
    SESSION = "session"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ItemStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"
    STALE = "stale"


class ContextType(str, Enum):
    DECISION = "decision"
    DISCUSSION = "discussion"
    ANNOUNCEMENT = "announcement"
    QUESTION = "question"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    CODE_REVIEW = "code_review"


# ── Base Item ────────────────────────────────────────────────────────────────


class BaseItem(BaseModel):
    """Shared fields for all knowledge base items."""

    id: str = Field(..., description="Unique identifier within the knowledge base")
    type: ItemType
    source: Source
    source_id: str = Field(..., description="Identifier at the source system")
    source_url: Optional[str] = Field(default=None, description="Permalink to the source")
    tags: list[str] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    related: list[str] = Field(default_factory=list, description="IDs of related items")


# ── Knowledge Item ───────────────────────────────────────────────────────────


class KnowledgeItem(BaseItem):
    """Immutable or stable facts about the project — extracted truths."""

    type: ItemType = ItemType.KNOWLEDGE
    title: str = Field(..., min_length=1, max_length=300)
    summary: str = Field(..., description="1-3 sentence summary")
    details: str = Field(default="", description="Full extracted knowledge")
    confidence: Confidence = Confidence.MEDIUM
    status: ItemStatus = ItemStatus.ACTIVE
    authors: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    context: str = Field(default="", description="Why this matters, origin context")
    implications: str = Field(default="", description="Actionable implications")
    verification: str = Field(default="", description="How to verify this is still correct")
    references: str = Field(default="", description="Links, commits, file paths")

    @field_validator("tags")
    @classmethod
    def tags_lowercase(cls, v: list[str]) -> list[str]:
        return [t.lower().strip() for t in v if t.strip()]

    def to_frontmatter(self) -> dict[str, Any]:
        """Serialize to YAML frontmatter dict."""
        return {
            "type": self.type.value,
            "source": self.source.value,
            "source_id": self.source_id,
            "source_url": self.source_url or "",
            "tags": self.tags,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "confidence": self.confidence.value,
            "status": self.status.value,
            "authors": self.authors,
            "depends_on": self.depends_on,
            "conflicts_with": self.conflicts_with,
            "related": self.related,
        }

    def to_markdown(self) -> str:
        """Render the item as a markdown file with YAML frontmatter."""
        import yaml

        fm = yaml.dump(self.to_frontmatter(), default_flow_style=False, allow_unicode=True, sort_keys=False)
        body = f"""# {self.title}

## Summary
{self.summary}

## Details
{self.details}

## Context
{self.context}

## Implications
{self.implications}

## Verification
{self.verification}

## References
{self.references}
"""
        return f"---\n{fm}---\n\n{body}"


# ── Memory Item ──────────────────────────────────────────────────────────────


class MemoryItem(BaseItem):
    """Conversation-derived context — decisions, preferences, discussion outcomes."""

    type: ItemType = ItemType.MEMORY
    title: str = Field(..., min_length=1, max_length=300)
    context_when_where: str = Field(default="", description="When/where this memory was formed")
    content: str = Field(..., description="The core decision, preference, or insight")
    rationale: str = Field(default="", description="Why this decision was made")
    importance: Importance = Importance.MEDIUM
    decay: Decay = Decay.PERMANENT
    participants: list[str] = Field(default_factory=list)
    context_type: ContextType = ContextType.DISCUSSION
    scope_decay: str = Field(default="", description="Validity window, expiry conditions")

    @field_validator("tags")
    @classmethod
    def tags_lowercase(cls, v: list[str]) -> list[str]:
        return [t.lower().strip() for t in v if t.strip()]

    def to_frontmatter(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "source": self.source.value,
            "source_id": self.source_id,
            "source_url": self.source_url or "",
            "tags": self.tags,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "importance": self.importance.value,
            "decay": self.decay.value,
            "participants": self.participants,
            "context_type": self.context_type.value,
            "related": self.related,
        }

    def to_markdown(self) -> str:
        import yaml

        fm = yaml.dump(self.to_frontmatter(), default_flow_style=False, allow_unicode=True, sort_keys=False)
        body = f"""# {self.title}

## Context — When & Where
{self.context_when_where}

## Decision / Preference / Insight
{self.content}

## Rationale
{self.rationale}

## Scope & Decay
{self.scope_decay}

## Related Memories
{", ".join(self.related) if self.related else "None"}
"""
        return f"---\n{fm}---\n\n{body}"


# ── Artifact Item ────────────────────────────────────────────────────────────


class ArtifactItem(BaseItem):
    """Tangible outputs — code snippets, configs, diagrams, generated files."""

    type: ItemType = ItemType.ARTIFACT
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="", description="What this artifact is")
    content: str = Field(..., description="The full artifact content")
    format: str = Field(default="text", description="code | config | diagram | document | data")
    language: str = Field(default="", description="Programming/markup language if code")
    size_bytes: int = Field(default=0)
    hash_sha256: str = Field(default="")
    mime_type: str = Field(default="text/plain")
    depends_on: list[str] = Field(default_factory=list)
    generated_by: str = Field(default="", description="Tool or process that generated this")
    usage: str = Field(default="", description="How to use this artifact")
    provenance: str = Field(default="", description="Origin chain")
    validation: str = Field(default="", description="How to verify correctness")

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of the content."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_frontmatter(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "source": self.source.value,
            "source_id": self.source_id,
            "source_url": self.source_url or "",
            "tags": self.tags,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "format": self.format,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "hash_sha256": self.hash_sha256,
            "mime_type": self.mime_type,
            "depends_on": self.depends_on,
            "generated_by": self.generated_by,
            "related": self.related,
        }

    def to_markdown(self) -> str:
        import yaml

        fm = yaml.dump(self.to_frontmatter(), default_flow_style=False, allow_unicode=True, sort_keys=False)
        lang = self.language or ""
        body = f"""# {self.title}

## Description
{self.description}

## Content
```{lang}
{self.content}
```

## Usage
{self.usage}

## Provenance
{self.provenance}

## Validation
{self.validation}
"""
        return f"---\n{fm}---\n\n{body}"


# ── Index Models ─────────────────────────────────────────────────────────────


class ScanStats(BaseModel):
    """Per-source scan statistics."""
    last_scan: Optional[datetime] = None
    items_found: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    error: Optional[str] = None


class IndexEntry(BaseModel):
    """A lightweight index entry pointing to a knowledge base file."""
    id: str
    type: ItemType
    source: Source
    source_id: str
    path: str = Field(..., description="Relative path to the markdown file")
    title: str
    tags: list[str] = Field(default_factory=list)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = Field(default="", description="SHA-256 of file content for change detection")


class MasterIndex(BaseModel):
    """The master index of all knowledge base entries."""
    version: str = "1.0.0"
    last_full_scan: Optional[datetime] = None
    scan_stats: dict[str, ScanStats] = Field(default_factory=dict)
    entries: list[IndexEntry] = Field(default_factory=list)
    tags: dict[str, list[str]] = Field(
        default_factory=dict, description="Tag → list of entry IDs"
    )
    cross_refs: dict[str, list[str]] = Field(
        default_factory=dict, description="Entry ID → list of related entry IDs"
    )

    def get_by_id(self, entry_id: str) -> Optional[IndexEntry]:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def get_by_tag(self, tag: str) -> list[IndexEntry]:
        entry_ids = self.tags.get(tag.lower(), [])
        return [e for e in self.entries if e.id in entry_ids]

    def get_by_source(self, source: Source) -> list[IndexEntry]:
        return [e for e in self.entries if e.source == source]

    def get_by_type(self, item_type: ItemType) -> list[IndexEntry]:
        return [e for e in self.entries if e.type == item_type]

    def search(self, query: str) -> list[IndexEntry]:
        """Simple case-insensitive search across titles and tags."""
        q = query.lower()
        results = []
        for entry in self.entries:
            if q in entry.title.lower():
                results.append(entry)
            elif any(q in tag.lower() for tag in entry.tags):
                results.append(entry)
        return results

    def add_entry(self, entry: IndexEntry) -> None:
        existing = self.get_by_id(entry.id)
        if existing:
            idx = self.entries.index(existing)
            self.entries[idx] = entry
        else:
            self.entries.append(entry)
        self._rebuild_tag_index()

    def remove_entry(self, entry_id: str) -> bool:
        entry = self.get_by_id(entry_id)
        if entry:
            self.entries.remove(entry)
            self._rebuild_tag_index()
            return True
        return False

    def _rebuild_tag_index(self) -> None:
        """Rebuild the tag → entry_id mapping."""
        self.tags = {}
        for entry in self.entries:
            for tag in entry.tags:
                tag_lower = tag.lower()
                if tag_lower not in self.tags:
                    self.tags[tag_lower] = []
                if entry.id not in self.tags[tag_lower]:
                    self.tags[tag_lower].append(entry.id)

    @property
    def total_entries(self) -> int:
        return len(self.entries)

    @property
    def total_tags(self) -> int:
        return len(self.tags)

    @property
    def all_tags(self) -> list[str]:
        return sorted(self.tags.keys())


# ── Scan Result ──────────────────────────────────────────────────────────────


class ScanResult(BaseModel):
    """Result of a single source scan."""
    source: Source
    started_at: datetime
    completed_at: Optional[datetime] = None
    items_scanned: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    new_items: list[KnowledgeItem | MemoryItem | ArtifactItem] = Field(default_factory=list)
    updated_items: list[KnowledgeItem | MemoryItem | ArtifactItem] = Field(default_factory=list)
    error: Optional[str] = None
    raw_snippets: list[str] = Field(default_factory=list, description="Raw findings for review")


class DiffResult(BaseModel):
    """Result of comparing new scan data against the existing index."""
    source: Source
    new: list[BaseItem] = Field(default_factory=list)
    updated: list[BaseItem] = Field(default_factory=list)
    unchanged: list[BaseItem] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list, description="IDs no longer present at source")
    duplicates_skipped: int = 0
