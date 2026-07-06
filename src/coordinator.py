"""
Coordinator Agent

The central orchestrator that manages the full knowledge base pipeline:
1. Loads system prompt
2. Sorts scanners by priority (highest first)
3. Skips sources not due for scanning (respects per-source check_interval_minutes)
4. Runs scans in priority order
5. Diffs new findings against existing index
6. Adds automatic 'source:{name}' tag to every persisted item
7. Updates the master index
8. Commits changes to git
"""

from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime, timezone, timedelta
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

logger = logging.getLogger(__name__)

# Registry of available scanner classes — extend here for new services
SCANNER_REGISTRY: dict[str, type[BaseScannerAgent]] = {
    "github": GitHubScannerAgent,
    "notion": NotionScannerAgent,
    "discord": DiscordScannerAgent,
    "telegram": TelegramScannerAgent,
}


def _register_scanner(name: str, cls: type[BaseScannerAgent]) -> None:
    """Register a new scanner class for a service name."""
    SCANNER_REGISTRY[name] = cls


class Coordinator:
    """
    Central coordinator for the knowledge base management system.

    Orchestrates the full pipeline: scan → extract → diff → index → persist.

    Features:
    - Per-source priority: higher = scanned first
    - Per-source check_interval_minutes: skips sources not yet due
    - Automatic source:{name} tag on every persisted item
    - Force-rescan capability (ignore interval)
    """

    def __init__(self, config_path: str | Path = "config.json"):
        self.config_path = Path(config_path)
        self.config: KBConfig = load_config(self.config_path)

        # Initialize components
        self.indexer = Indexer(
            base_path=self.config.storage.base_path,
            index_file=self.config.storage.index_file,
        )
        self.diff_engine: Optional[DiffEngine] = None

        # System prompt path
        self.system_prompt_path = Path("system_prompt.md")
        self.system_prompt: str = self._load_system_prompt()

        # Scanner agents (initialized lazily)
        self._scanners: dict[str, BaseScannerAgent] = {}

        # Per-source last scan timestamps (loaded from index scan_stats)
        self._last_scan_times: dict[str, datetime] = self._load_last_scan_times()

    def _load_system_prompt(self) -> str:
        """Load the coordinator system prompt from system_prompt.md."""
        if self.system_prompt_path.exists():
            return self.system_prompt_path.read_text(encoding="utf-8")
        logger.warning("system_prompt.md not found at %s", self.system_prompt_path)
        return ""

    def _load_last_scan_times(self) -> dict[str, datetime]:
        """Load last scan timestamps from the index's scan_stats."""
        result: dict[str, datetime] = {}
        for svc_name, stats in self.indexer.index.scan_stats.items():
            if stats.last_scan:
                result[svc_name] = stats.last_scan
        return result

    def _is_scan_due(self, service_name: str, force: bool = False) -> bool:
        """
        Check if a service is due for scanning based on its check_interval_minutes.

        Args:
            service_name: Service name from config
            force: If True, always consider the scan due

        Returns:
            True if the scan should run
        """
        if force:
            return True

        svc_config = self.config.services.get(service_name)
        if not svc_config or not svc_config.enabled:
            return False

        interval = svc_config.check_interval_minutes
        last_scan = self._last_scan_times.get(service_name)

        if last_scan is None:
            # Never scanned — due immediately
            return True

        due_time = last_scan + timedelta(minutes=interval)
        return datetime.now(timezone.utc) >= due_time

    def _get_sorted_services(self) -> list[tuple[str, int]]:
        """
        Get enabled services sorted by priority (highest first).

        Returns:
            List of (service_name, priority) tuples, sorted descending.
        """
        enabled = get_enabled_services(self.config)
        with_priority = [
            (name, svc.priority) for name, svc in enabled.items()
        ]
        # Sort: highest priority first, then alphabetically for ties
        with_priority.sort(key=lambda x: (-x[1], x[0]))
        return with_priority

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

        scanner_cls = SCANNER_REGISTRY.get(service_name)
        if scanner_cls is None:
            logger.warning("No scanner implementation for service: %s", service_name)
            return None

        scanner = scanner_cls(service_config, skill_path)
        self._scanners[service_name] = scanner
        return scanner

    def run_full_scan(self, force: bool = False, sources: Optional[list[str]] = None) -> dict[str, Any]:
        """
        Execute a complete scan cycle across all enabled services.

        Args:
            force: If True, scan all sources regardless of check_interval_minutes
            sources: Optional list of source names to scan. If None, scan all enabled.

        Returns:
            Summary dict with scan results per service.
        """
        logger.info("=" * 60)
        if force:
            logger.info("Starting FORCED full knowledge base scan cycle")
        else:
            logger.info("Starting full knowledge base scan cycle")
        logger.info("=" * 60)

        # Refresh diff engine with current index
        self.indexer.reload()
        self.diff_engine = DiffEngine(self.indexer.index)

        # Get sorted services
        sorted_services = self._get_sorted_services()

        # Filter by sources if specified
        if sources:
            source_set = set(sources)
            sorted_services = [(n, p) for n, p in sorted_services if n in source_set]

        logger.info(
            "Services by priority: %s",
            ", ".join(f"{n}(p={p})" for n, p in sorted_services),
        )

        summary: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "force": force,
            "services": {},
            "totals": {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0},
        }

        for service_name, priority in sorted_services:
            # Check if this source is due for scanning
            if not self._is_scan_due(service_name, force=force):
                svc_config = self.config.services.get(service_name)
                interval = svc_config.check_interval_minutes if svc_config else "?"
                last_scan = self._last_scan_times.get(service_name)
                logger.info(
                    "--- Skipping %s (priority=%d): not due yet (interval=%d min, last_scan=%s) ---",
                    service_name, priority, interval,
                    last_scan.isoformat() if last_scan else "never",
                )
                summary["services"][service_name] = {
                    "status": "skipped",
                    "reason": f"Not due yet (interval={interval}min)",
                    "last_scan": last_scan.isoformat() if last_scan else None,
                    "new": 0, "updated": 0, "unchanged": 0,
                }
                summary["totals"]["skipped"] += 1
                continue

            logger.info("--- Scanning %s (priority=%d) ---", service_name, priority)
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

        # Log to activity log
        self._log_scan_activity(summary)

        self._log_summary(summary)
        self._commit_changes(summary)

        return summary

    def rescan_source(self, source_name: str) -> dict[str, Any]:
        """
        Force-rescan a single source immediately.

        Args:
            source_name: Name of the source to rescan

        Returns:
            Summary dict for that source
        """
        logger.info("=== Force rescan requested for: %s ===", source_name)
        return self.run_full_scan(force=True, sources=[source_name])

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

        # Update last scan time
        self._last_scan_times[service_name] = datetime.now(timezone.utc)

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

        Automatically adds 'source:{name}' tag to every item for origin tracking.
        """
        try:
            # ── AUTOMATIC SOURCE ORIGIN TAG ──────────────────────────
            source_tag = f"source:{item.source.value}"
            if source_tag not in item.tags:
                item.tags.append(source_tag)

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
            if svc_data.get("status") == "skipped":
                logger.info("  %s: SKIPPED — %s", svc_name, svc_data.get("reason", ""))
            elif svc_data.get("error"):
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
            "Total: %d new, %d updated, %d unchanged, %d skipped, %d errors",
            totals.get("new", 0),
            totals.get("updated", 0),
            totals.get("unchanged", 0),
            totals.get("skipped", 0),
            totals.get("errors", 0),
        )
        logger.info(
            "Index: %d entries, %d tags",
            summary.get("total_entries", 0),
            summary.get("total_tags", 0),
        )

    def _log_scan_activity(self, summary: dict[str, Any]) -> None:
        """Log scan results to the persistent activity log."""
        try:
            from .mcp_server.activity_logger import get_activity_logger

            alog = get_activity_logger()
            totals = summary.get("totals", {})

            for svc_name, svc_data in summary.get("services", {}).items():
                if svc_data.get("status") == "skipped":
                    alog.log_scan_event("scan_skipped", svc_name,
                                        reason=svc_data.get("reason", ""))
                elif svc_data.get("error"):
                    alog.log_error("scanner", svc_data["error"],
                                   component=f"scanner.{svc_name}")
                else:
                    alog.log_scan_event(
                        "scan_complete", svc_name,
                        new=svc_data.get("new", 0),
                        updated=svc_data.get("updated", 0),
                        unchanged=svc_data.get("unchanged", 0),
                    )

            alog.log("scan_cycle_complete", {
                "new": totals.get("new", 0),
                "updated": totals.get("updated", 0),
                "unchanged": totals.get("unchanged", 0),
                "skipped": totals.get("skipped", 0),
                "errors": totals.get("errors", 0),
                "total_entries": summary.get("total_entries", 0),
            })
        except Exception:
            logger.debug("Failed to log scan activity (activity logger not initialized?)")
