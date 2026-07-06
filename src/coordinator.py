"""
Coordinator Agent

The central orchestrator that manages the full knowledge base pipeline:
1. Loads system prompt
2. Initializes all scanner agents
3. Runs scans in sequence
4. Diffs new findings against existing index
5. Persists new/updated items to filesystem
6. Updates the master index
7. Commits changes to git
"""

from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import KBConfig, get_enabled_services, load_config
from .agents.base import BaseScannerAgent
from .agents.github_scanner import GitHubScannerAgent
from .agents.notion_scanner import NotionScannerAgent
from .agents.discord_scanner import DiscordScannerAgent
from .agents.telegram_scanner import TelegramScannerAgent
from .storage.indexer import Indexer
from .storage.diff import DiffEngine, compute_item_hash
from .storage.models import (
    ArtifactItem,
    BaseItem,
    IndexEntry,
    ItemType,
    KnowledgeItem,
    MasterIndex,
    MemoryItem,
    ScanResult,
    Source,
)
from .storage.templates import TemplateEngine

logger = logging.getLogger(__name__)


class Coordinator:
    """
    Central coordinator for the knowledge base management system.

    Orchestrates the full pipeline: scan → extract → diff → index → persist.
    """

    def __init__(self, config_path: str | Path = "config.json"):
        self.config_path = Path(config_path)
        self.config: KBConfig = load_config(self.config_path)

        # Initialize components
        self.indexer = Indexer(
            base_path=self.config.storage.base_path,
            index_file=self.config.storage.index_file,
        )
        self.template_engine = TemplateEngine()
        self.diff_engine: Optional[DiffEngine] = None

        # System prompt path
        self.system_prompt_path = Path("system_prompt.md")
        self.system_prompt: str = self._load_system_prompt()

        # Scanner agents (initialized lazily)
        self._scanners: dict[str, BaseScannerAgent] = {}

    def _load_system_prompt(self) -> str:
        """Load the coordinator system prompt from system_prompt.md."""
        if self.system_prompt_path.exists():
            return self.system_prompt_path.read_text(encoding="utf-8")
        logger.warning("system_prompt.md not found at %s", self.system_prompt_path)
        return ""

    def _get_scanner(self, service_name: str) -> Optional[BaseScannerAgent]:
        """Get or create a scanner agent for a given service."""
        if service_name in self._scanners:
            return self._scanners[service_name]

        service_config = self.config.services.get(service_name)
        if not service_config:
            logger.warning("No config for service: %s", service_name)
            return None

        skill_dir = Path("skills") / f"scan-{service_name}"
        skill_path = str(skill_dir / "skill.md") if skill_dir.exists() else None

        scanner_map = {
            "github": GitHubScannerAgent,
            "notion": NotionScannerAgent,
            "discord": DiscordScannerAgent,
            "telegram": TelegramScannerAgent,
        }

        scanner_cls = scanner_map.get(service_name)
        if scanner_cls is None:
            logger.warning("No scanner implementation for service: %s", service_name)
            return None

        scanner = scanner_cls(service_config, skill_path)
        self._scanners[service_name] = scanner
        return scanner

    def run_full_scan(self) -> dict[str, Any]:
        """
        Execute a complete scan cycle across all enabled services.

        Returns:
            Summary dict with scan results per service.
        """
        logger.info("=" * 60)
        logger.info("Starting full knowledge base scan cycle")
        logger.info("=" * 60)

        # Refresh diff engine with current index
        self.diff_engine = DiffEngine(self.indexer.index)

        enabled = get_enabled_services(self.config)
        logger.info("Enabled services: %s", list(enabled.keys()))

        summary: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "services": {},
            "totals": {"new": 0, "updated": 0, "unchanged": 0, "errors": 0},
        }

        for service_name in enabled:
            logger.info("--- Scanning %s ---", service_name)
            service_summary = self._scan_service(service_name)
            summary["services"][service_name] = service_summary

            for key in ["new", "updated", "unchanged"]:
                summary["totals"][key] += service_summary.get(key, 0)
            if service_summary.get("error"):
                summary["totals"]["errors"] += 1

        # Update last full scan timestamp
        self.indexer.update_last_full_scan()
        self.indexer.save()

        summary["completed_at"] = datetime.now(timezone.utc).isoformat()
        summary["total_entries"] = self.indexer.total_entries
        summary["total_tags"] = self.indexer.total_tags

        self._log_summary(summary)
        self._commit_changes(summary)

        return summary

    def _scan_service(self, service_name: str) -> dict[str, Any]:
        """Run a scan for a single service and process results."""
        scanner = self._get_scanner(service_name)
        if scanner is None:
            return {"error": f"No scanner for {service_name}", "new": 0, "updated": 0, "unchanged": 0}

        # Run the scanner
        scan_result = scanner.scan()

        if scan_result.error:
            logger.error("Scan error for %s: %s", service_name, scan_result.error)
            return {
                "error": scan_result.error,
                "new": 0,
                "updated": 0,
                "unchanged": 0,
            }

        # Diff against existing index
        source = scanner.source
        all_items = list(scan_result.new_items) + list(scan_result.updated_items)

        if all_items and self.diff_engine:
            diff = self.diff_engine.analyze(source, all_items)

            # Persist new items
            for item in diff.new:
                self._persist_item(item)

            # Update existing items
            for item in diff.updated:
                self._persist_item(item)

            # Mark removed items as stale
            for removed_id in diff.removed:
                entry = self.indexer.get_entry(removed_id)
                if entry:
                    logger.info("Marking as stale (removed from source): %s", removed_id)

            result = {
                "new": len(diff.new),
                "updated": len(diff.updated),
                "unchanged": len(diff.unchanged),
                "removed": len(diff.removed),
                "duplicates_skipped": diff.duplicates_skipped,
            }
        else:
            result = {
                "new": len(scan_result.new_items),
                "updated": len(scan_result.updated_items),
                "unchanged": scan_result.items_scanned,
            }

            # Persist all items directly if no diff engine
            for item in scan_result.new_items:
                self._persist_item(item)

        self.indexer.save()
        return result

    def _persist_item(self, item: BaseItem) -> None:
        """
        Write a knowledge base item to the filesystem and update the index.
        """
        try:
            # Render to markdown
            if isinstance(item, KnowledgeItem):
                content = item.to_markdown()
            elif isinstance(item, MemoryItem):
                content = item.to_markdown()
            elif isinstance(item, ArtifactItem):
                content = item.to_markdown()
            else:
                logger.warning("Unknown item type: %s", type(item))
                return

            # Compute hash
            content_hash = compute_item_hash(content)

            # Determine file path
            file_path = self.indexer.make_file_path(item.id, item.type)

            # Write file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            # Create index entry
            entry = IndexEntry(
                id=item.id,
                type=item.type,
                source=item.source,
                source_id=item.source_id,
                path=str(file_path.relative_to(self.indexer.base_path)),
                title=item.title if hasattr(item, "title") else item.id,
                tags=item.tags,
                created=item.created,
                updated=item.updated,
                content_hash=content_hash,
            )

            self.indexer.add_or_update(entry)
            logger.info("Persisted: %s → %s", item.id, file_path)

        except Exception as e:
            logger.exception("Failed to persist item %s: %s", item.id, e)

    def _commit_changes(self, summary: dict[str, Any]) -> None:
        """
        Commit knowledge base changes to git.
        Only stages changes in the knowledge/ directory.
        """
        try:
            knowledge_dir = self.indexer.base_path

            # Check if there are changes
            result = subprocess.run(
                ["git", "status", "--porcelain", str(knowledge_dir)],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            if not result.stdout.strip():
                logger.info("No changes to commit.")
                return

            # Stage changes
            subprocess.run(
                ["git", "add", str(knowledge_dir)],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            # Build commit message
            totals = summary.get("totals", {})
            sources = list(summary.get("services", {}).keys())
            msg = (
                f"kb: scan {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} — "
                f"{totals.get('new', 0)} new, {totals.get('updated', 0)} updated "
                f"from {', '.join(sources)}"
            )

            subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            logger.info("Committed: %s", msg)

        except FileNotFoundError:
            logger.debug("Git not available — skipping commit")
        except Exception as e:
            logger.warning("Failed to commit changes: %s", e)

    def _log_summary(self, summary: dict[str, Any]) -> None:
        """Log a human-readable scan summary."""
        logger.info("=" * 60)
        logger.info("Scan cycle complete")
        logger.info("=" * 60)

        for svc_name, svc_data in summary.get("services", {}).items():
            if svc_data.get("error"):
                logger.info("  %s: ERROR — %s", svc_name, svc_data["error"])
            else:
                logger.info(
                    "  %s: %d new, %d updated, %d unchanged%s",
                    svc_name,
                    svc_data.get("new", 0),
                    svc_data.get("updated", 0),
                    svc_data.get("unchanged", 0),
                    f", {svc_data.get('duplicates_skipped', 0)} dupes skipped"
                    if svc_data.get("duplicates_skipped") else "",
                )

        totals = summary.get("totals", {})
        logger.info(
            "Total: %d new, %d updated, %d unchanged, %d errors",
            totals.get("new", 0),
            totals.get("updated", 0),
            totals.get("unchanged", 0),
            totals.get("errors", 0),
        )
        logger.info(
            "Index: %d entries, %d tags",
            summary.get("total_entries", 0),
            summary.get("total_tags", 0),
        )
