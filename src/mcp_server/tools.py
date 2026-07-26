"""
MCP Tool Definitions

Defines the tools exposed by the KB MCP server to external coding agents.
Each tool is implemented as a standalone function that operates on the knowledge base.

Includes admin tools: rescan_kb (trigger knowledge refresh), reload_index (reload from disk)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)

# ── Reference to coordinator (set by server on init) ───────────────────────
_coordinator: Any = None


def set_coordinator(coordinator: Any) -> None:
    """Inject the coordinator reference for admin tools like rescan_kb."""
    global _coordinator
    _coordinator = coordinator


# ── Reference to chat agent (set by server on init) ────────────────────────
_chat_agent: Any = None


def set_chat_agent(agent: Any) -> None:
    """Inject the ChatAgent reference for the ask_kb tool."""
    global _chat_agent
    _chat_agent = agent


# ════════════════════════════════════════════════════════════════════════════
#  Query Tools
# ════════════════════════════════════════════════════════════════════════════


def search_kb(
    index_path: str,
    query: str = "",
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
    item_type: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Search the knowledge base by full-text query and/or tag filters.

    Args:
        index_path: Path to knowledge/index.json
        query: Full-text search query
        tags: Filter by one or more tags
        source: Filter by source (github, notion, discord, telegram)
        item_type: Filter by item type (knowledge, memory, artifact)
        limit: Maximum results to return
    """
    try:
        from ..storage.indexer import Indexer
        from ..storage.models import ItemType, Source

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.load()

        results = indexer.index.entries

        # Apply filters
        if query:
            results = indexer.search(query)
        if tags:
            tag_set = {t.lower() for t in tags}
            results = [e for e in results if tag_set & {t.lower() for t in e.tags}]
        if source:
            try:
                src = Source(source)
                results = [e for e in results if e.source == src]
            except ValueError:
                pass
        if item_type:
            try:
                it = ItemType(item_type)
                results = [e for e in results if e.type == it]
            except ValueError:
                pass

        # Sort by updated date, newest first
        results = sorted(results, key=lambda e: e.updated or e.created, reverse=True)

        # Apply limit
        results = results[:limit]

        # Format output
        output = {
            "query": query,
            "filters": {"tags": tags, "source": source, "type": item_type},
            "total_results": len(results),
            "results": [
                {
                    "id": e.id,
                    "type": e.type.value,
                    "source": e.source.value,
                    "title": e.title,
                    "tags": e.tags,
                    "path": e.path,
                    "updated": e.updated.isoformat() if e.updated else None,
                }
                for e in results
            ],
        }

        return json.dumps(output, indent=2, default=str)

    except Exception as e:
        logger.exception("search_kb failed")
        return json.dumps({"error": str(e)})


def get_knowledge(index_path: str, item_id: str) -> str:
    """
    Retrieve a specific knowledge/memory/artifact item by ID.
    Returns the full markdown content.

    Args:
        index_path: Path to knowledge/index.json
        item_id: The unique ID of the item to retrieve
    """
    try:
        from ..storage.indexer import Indexer

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.load()

        entry = indexer.get_entry(item_id)
        if not entry:
            return json.dumps({"error": f"Item not found: {item_id}"})

        file_path = (Path(indexer.base_path) / entry.path).resolve()
        # Prevent path traversal: resolved path must be within base_path
        if not str(file_path).startswith(str(Path(indexer.base_path).resolve())):
            logger.warning("Path traversal attempt blocked: %s", item_id)
            return json.dumps({"error": "Access denied"})

        if not file_path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        content = file_path.read_text(encoding="utf-8")

        return json.dumps({
            "id": entry.id,
            "type": entry.type.value,
            "source": entry.source.value,
            "title": entry.title,
            "tags": entry.tags,
            "path": entry.path,
            "content": content,
            "updated": entry.updated.isoformat() if entry.updated else None,
        }, indent=2, default=str)

    except Exception as e:
        logger.exception("get_knowledge failed")
        return json.dumps({"error": str(e)})


def list_tags(index_path: str) -> str:
    """
    List all tags in the knowledge base with their counts.

    Args:
        index_path: Path to knowledge/index.json
    """
    try:
        from ..storage.indexer import Indexer

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.load()

        tag_counts = {}
        for tag, entry_ids in indexer.index.tags.items():
            tag_counts[tag] = len(entry_ids)

        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

        return json.dumps({
            "total_tags": len(sorted_tags),
            "tags": [{"tag": t, "count": c} for t, c in sorted_tags],
        }, indent=2)

    except Exception as e:
        logger.exception("list_tags failed")
        return json.dumps({"error": str(e)})


def list_sources(index_path: str) -> str:
    """
    List all data sources with statistics, priority, and scan status.

    Args:
        index_path: Path to knowledge/index.json
    """
    try:
        from ..storage.indexer import Indexer

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.load()

        sources = {}
        for entry in indexer.index.entries:
            src = entry.source.value
            if src not in sources:
                sources[src] = {"total": 0, "by_type": {}}
            sources[src]["total"] += 1
            type_name = entry.type.value
            sources[src]["by_type"][type_name] = sources[src]["by_type"].get(type_name, 0) + 1

        # Include scan stats with last_scan info
        scan_info = {}
        for src_name, stats in indexer.index.scan_stats.items():
            scan_info[src_name] = {
                "last_scan": stats.last_scan.isoformat() if stats.last_scan else None,
                "items_found": stats.items_found,
                "items_new": stats.items_new,
                "error": stats.error,
            }

        return json.dumps({
            "sources": sources,
            "scan_info": scan_info,
            "total_entries": indexer.total_entries,
            "last_full_scan": indexer.index.last_full_scan.isoformat() if indexer.index.last_full_scan else None,
        }, indent=2, default=str)

    except Exception as e:
        logger.exception("list_sources failed")
        return json.dumps({"error": str(e)})


def get_kb_stats(index_path: str) -> str:
    """
    Get overall knowledge base statistics.

    Args:
        index_path: Path to knowledge/index.json
    """
    try:
        from ..storage.indexer import Indexer
        from ..storage.models import ItemType, Source

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.load()
        idx = indexer.index

        return json.dumps({
            "version": idx.version,
            "total_entries": indexer.total_entries,
            "total_tags": indexer.total_tags,
            "last_full_scan": idx.last_full_scan.isoformat() if idx.last_full_scan else None,
            "by_type": {
                "knowledge": len(indexer.get_by_type(ItemType("knowledge"))),
                "memory": len(indexer.get_by_type(ItemType("memory"))),
                "artifact": len(indexer.get_by_type(ItemType("artifact"))),
            },
            "by_source": {
                src.value: len(indexer.get_by_source(src))
                for src in Source
            },
            "scan_stats": {
                src: {
                    "last_scan": stats.last_scan.isoformat() if stats.last_scan else None,
                    "items_found": stats.items_found,
                    "items_new": stats.items_new,
                    "error": stats.error,
                }
                for src, stats in idx.scan_stats.items()
            },
        }, indent=2, default=str)

    except Exception as e:
        logger.exception("get_kb_stats failed")
        return json.dumps({"error": str(e)})


def ask_kb(index_path: str, question: str, session_id: Optional[str] = None) -> str:
    """
    Ask a natural-language question and get an answer from an agent with
    real tool-calling access to the knowledge base (search_kb, get_knowledge,
    etc.) — grounded and source-cited, not just raw search results. Pass the
    returned session_id back in to continue the same conversation.

    Args:
        index_path: Path to knowledge/index.json (unused directly — the
            chat agent reaches the KB via its own registered MCP tools)
        question: The question to ask
        session_id: Continue a prior conversation; omit to start a new one

    Returns:
        JSON: {"answer": ..., "session_id": ...} or {"error": ...}
    """
    try:
        if _chat_agent is None:
            return json.dumps({
                "error": "Chat agent not initialized. The MCP server must be started with chat support.",
                "status": "unavailable",
            })

        answer, new_session_id = _chat_agent.ask(question, session_id=session_id)
        return json.dumps({"answer": answer, "session_id": new_session_id}, indent=2, default=str)

    except Exception as e:
        logger.exception("ask_kb failed")
        return json.dumps({"error": str(e)})


# ════════════════════════════════════════════════════════════════════════════
#  Admin Tools
# ════════════════════════════════════════════════════════════════════════════


def rescan_kb(
    index_path: str,
    source: Optional[str] = None,
    force: bool = True,
) -> str:
    """
    Trigger a knowledge base rescan — re-index from external sources immediately.

    Args:
        index_path: Path to knowledge/index.json (unused by rescan, but passed by MCP convention)
        source: Specific source to rescan (github, notion, discord, telegram).
                If None, rescans all sources.
        force: Force rescan regardless of check_interval_minutes (default: True)

    Returns:
        JSON with scan results summary.
    """
    try:
        if _coordinator is None:
            return json.dumps({
                "error": "Coordinator not initialized. The MCP server must be started with coordinator support.",
                "status": "unavailable",
            })

        sources = [source] if source else None

        logger.info("MCP tool: rescan_kb triggered (source=%s, force=%s)", source, force)
        summary = _coordinator.run_full_scan(force=force, sources=sources)

        return json.dumps({
            "status": "completed",
            "started_at": summary.get("started_at"),
            "completed_at": summary.get("completed_at"),
            "services": summary.get("services", {}),
            "totals": summary.get("totals", {}),
            "total_entries": summary.get("total_entries"),
        }, indent=2, default=str)

    except Exception as e:
        logger.exception("rescan_kb failed")
        return json.dumps({"error": str(e), "status": "failed"})


def reload_index(index_path: str) -> str:
    """
    Reload the knowledge base index from disk.
    Useful after external modifications to the knowledge store.

    Args:
        index_path: Path to knowledge/index.json

    Returns:
        JSON confirming reload with current stats.
    """
    try:
        from ..storage.indexer import Indexer

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.reload()

        return json.dumps({
            "status": "reloaded",
            "total_entries": indexer.total_entries,
            "total_tags": indexer.total_tags,
            "last_full_scan": indexer.index.last_full_scan.isoformat() if indexer.index.last_full_scan else None,
        }, indent=2, default=str)

    except Exception as e:
        logger.exception("reload_index failed")
        return json.dumps({"error": str(e), "status": "failed"})


def export_kb(index_path: str) -> str:
    """
    Export the entire knowledge base as a single portable JSON bundle
    (every index entry plus its rendered markdown content). Feed the
    returned bundle to import_kb (here, or on another KB instance) to
    restore it.

    Args:
        index_path: Path to knowledge/index.json

    Returns:
        JSON bundle: {"format_version": 1, "exported_at": ..., "entries": [...]}
    """
    try:
        from ..kb_export import export_bundle
        from ..storage.indexer import Indexer

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.load()

        bundle = export_bundle(indexer)
        return json.dumps(bundle, indent=2, default=str)

    except Exception as e:
        logger.exception("export_kb failed")
        return json.dumps({"error": str(e)})


def import_kb(index_path: str, bundle_json: str, mode: str = "merge") -> str:
    """
    Import a knowledge base bundle (as produced by export_kb). Recomputes
    file paths and content hashes server-side — never trusts the bundle's
    own declared path or hash.

    Args:
        index_path: Path to knowledge/index.json
        bundle_json: The JSON bundle text (as returned by export_kb)
        mode: "merge" (default, upsert only) or "replace" (also deletes
              local entries absent from the bundle)

    Returns:
        JSON summary of what was added/updated/unchanged/deleted.
    """
    try:
        from ..kb_export import import_bundle as _import_bundle
        from ..storage.indexer import Indexer

        bundle = json.loads(bundle_json)

        indexer = Indexer(base_path=str(Path(index_path).parent), index_file=Path(index_path).name)
        indexer.load()

        summary = _import_bundle(indexer, bundle, mode=mode)
        indexer.save()

        return json.dumps({"status": "completed", "mode": mode, **summary}, indent=2, default=str)

    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": str(e), "status": "failed"})
    except Exception as e:
        logger.exception("import_kb failed")
        return json.dumps({"error": str(e), "status": "failed"})


# ════════════════════════════════════════════════════════════════════════════
#  Tool Definitions Registry
# ════════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    # ── Query tools ────────────────────────────────────────────────────────
    {
        "name": "search_kb",
        "description": "Search the GymBoost knowledge base by query, tags, source, or type. Returns matching entries with metadata including source origin tags.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
                "query": {"type": "string", "description": "Full-text search query"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
                "source": {"type": "string", "description": "Filter by source: github, notion, discord, telegram"},
                "item_type": {"type": "string", "description": "Filter by type: knowledge, memory, artifact"},
                "limit": {"type": "integer", "description": "Max results (default: 20)"},
            },
        },
    },
    {
        "name": "get_knowledge",
        "description": "Retrieve a specific knowledge base item by ID. Returns full markdown content with source origin.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
                "item_id": {"type": "string", "description": "The unique ID of the item"},
            },
            "required": ["index_path", "item_id"],
        },
    },
    {
        "name": "list_tags",
        "description": "List all tags in the knowledge base with their item counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
            },
            "required": ["index_path"],
        },
    },
    {
        "name": "list_sources",
        "description": "List all data sources with entry counts, scan status, and last-scan timestamps.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
            },
            "required": ["index_path"],
        },
    },
    {
        "name": "get_kb_stats",
        "description": "Get overall knowledge base statistics including per-source scan stats and last-scan times.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
            },
            "required": ["index_path"],
        },
    },
    {
        "name": "ask_kb",
        "description": "Ask a natural-language question about the GymBoost project. Answered by an agent with real tool access to search/read the knowledge base, grounded and source-cited. Pass back the returned session_id to continue the same conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
                "question": {"type": "string", "description": "The question to ask"},
                "session_id": {"type": "string", "description": "Continue a prior conversation (from a previous ask_kb response); omit to start a new one"},
            },
            "required": ["index_path", "question"],
        },
    },
    {
        "name": "export_kb",
        "description": "Export the entire knowledge base as a single portable JSON bundle (every entry + its full content). Feed the result to import_kb to restore it, here or on another KB instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
            },
            "required": ["index_path"],
        },
    },
    # ── Admin tools ────────────────────────────────────────────────────────
    {
        "name": "rescan_kb",
        "description": "Trigger an immediate knowledge base rescan — re-index from external sources (GitHub, Notion, Discord, Telegram). Use 'source' parameter to rescan a single source, or omit to rescan all.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
                "source": {
                    "type": "string",
                    "description": "Specific source to rescan: github, notion, discord, or telegram. If omitted, rescans all.",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force rescan regardless of check_interval_minutes (default: true)",
                },
            },
            "required": ["index_path"],
        },
    },
    {
        "name": "reload_index",
        "description": "Reload the knowledge base index from disk. Useful if knowledge files were modified externally.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
            },
            "required": ["index_path"],
        },
    },
    {
        "name": "import_kb",
        "description": "Import a knowledge base bundle produced by export_kb, merging it into (or replacing) this knowledge base.",
        "parameters": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string", "description": "Path to knowledge/index.json"},
                "bundle_json": {"type": "string", "description": "The JSON bundle text, as returned by export_kb"},
                "mode": {
                    "type": "string",
                    "description": "'merge' (default, upsert only) or 'replace' (also deletes local entries absent from the bundle)",
                },
            },
            "required": ["index_path", "bundle_json"],
        },
    },
]
