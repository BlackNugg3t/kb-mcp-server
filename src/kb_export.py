"""
Knowledge Base Export / Import

Bundles the master index + every entry's rendered markdown content into a
single portable JSON document, and restores it back. Used for backup,
migration, and agent-to-agent context transfer (see the export_kb/import_kb
MCP tools in src/mcp_server/tools.py and the export/import CLI subcommands
in src/main.py).

Security: import never trusts a bundle's embedded `path` or `content_hash` —
both are recomputed server-side, the same way the scan pipeline already
computes them, so a malicious/stale bundle cannot write outside the
knowledge base root or spoof a change-detection hash.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .storage.indexer import Indexer
from .storage.models import IndexEntry

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1


def export_bundle(indexer: Indexer) -> dict[str, Any]:
    """Bundle every index entry and its markdown content into one JSON-serializable dict."""
    entries = []
    for entry in indexer.index.entries:
        file_path = indexer.base_path / entry.path
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Skipping %s in export: could not read %s (%s)", entry.id, file_path, e)
            continue
        entries.append({"entry": entry.model_dump(mode="json"), "content": content})

    return {
        "format_version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }


def import_bundle(indexer: Indexer, bundle: dict[str, Any], mode: str = "merge") -> dict[str, int]:
    """
    Restore entries from an export bundle.

    mode="merge" (default): upsert entries from the bundle; skip if content
    is unchanged; leaves existing entries not present in the bundle alone.
    mode="replace": also deletes local entries (and their files) that are
    absent from the bundle, so the result matches the bundle exactly.
    """
    if mode not in ("merge", "replace"):
        raise ValueError(f"Invalid import mode: {mode!r} (expected 'merge' or 'replace')")

    summary = {"added": 0, "updated": 0, "unchanged": 0, "deleted": 0, "skipped_invalid": 0}
    bundle_ids: set[str] = set()

    for item in bundle.get("entries", []):
        raw_entry = item.get("entry", {})
        content = item.get("content", "")

        try:
            candidate = IndexEntry(**raw_entry)
        except Exception as e:
            logger.warning("Skipping invalid bundle entry %r: %s", raw_entry.get("id"), e)
            summary["skipped_invalid"] += 1
            continue

        bundle_ids.add(candidate.id)

        # Never trust the bundle's own path or hash — recompute both from
        # the validated id/type and the actual content, exactly like scanning does.
        file_path = indexer.make_file_path(candidate.id, candidate.type)
        content_hash = Indexer.compute_content_hash(content)

        existing = indexer.get_entry(candidate.id)
        if existing and existing.content_hash == content_hash:
            summary["unchanged"] += 1
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        entry = candidate.model_copy(
            update={
                "path": str(file_path.relative_to(indexer.base_path)),
                "content_hash": content_hash,
            }
        )
        indexer.add_or_update(entry)
        summary["updated" if existing else "added"] += 1

    if mode == "replace":
        existing_ids = {e.id for e in indexer.index.entries}
        for stale_id in existing_ids - bundle_ids:
            stale_entry = indexer.get_entry(stale_id)
            if stale_entry is None:
                continue
            stale_path = indexer.base_path / stale_entry.path
            if stale_path.exists():
                stale_path.unlink()
            indexer.remove(stale_id)
            summary["deleted"] += 1

    return summary
