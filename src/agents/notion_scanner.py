"""
Notion Scanner Agent

Scans Notion pages and databases for documentation, specifications,
and project-related information.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import ServiceConfig
from ..storage.models import (
    ArtifactItem,
    BaseItem,
    Confidence,
    ItemStatus,
    ItemType,
    KnowledgeItem,
    ScanResult,
    Source,
)
from .base import BaseScannerAgent

logger = logging.getLogger(__name__)


class NotionScannerAgent(BaseScannerAgent):
    """Read-only scanner for Notion workspaces via MCP."""

    source = Source.NOTION

    def __init__(self, service_config: ServiceConfig, skill_path: str | None = None):
        super().__init__(service_config, skill_path)
        self.databases = service_config.databases
        self.page_filters = service_config.page_filters

    def scan(self) -> ScanResult:
        return self._safe_scan(self._do_scan)

    def _do_scan(self) -> ScanResult:
        """Execute the full Notion scan."""
        started_at = datetime.now(timezone.utc)
        all_items: list[BaseItem] = []
        all_snippets: list[str] = []
        total_scanned = 0

        agent = self._init_agent()

        # Scan pages matching the search query
        search_query = self.page_filters.get("search_query", "")
        if search_query:
            try:
                items, snippets, count = self._scan_pages(agent, search_query)
                all_items.extend(items)
                all_snippets.extend(snippets)
                total_scanned += count
            except Exception as e:
                logger.error("Failed to scan Notion pages: %s", e)

        # Scan configured databases
        for db_id in self.databases:
            try:
                items, snippets, count = self._scan_database(agent, db_id)
                all_items.extend(items)
                all_snippets.extend(snippets)
                total_scanned += count
            except Exception as e:
                logger.error("Failed to scan Notion database %s: %s", db_id, e)

        return self._make_scan_result(
            items=all_items,
            raw_snippets=all_snippets,
            started_at=started_at,
            items_scanned=total_scanned,
        )

    def _scan_pages(self, agent: Any, query: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan Notion pages matching a search query."""
        items: list[BaseItem] = []
        snippets: list[str] = []
        count = 0
        logger.info("Would scan Notion pages for query: %s (requires running Harnext agent)", query)
        return items, snippets, count

    def _scan_database(self, agent: Any, db_id: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan a specific Notion database."""
        items: list[BaseItem] = []
        snippets: list[str] = []
        count = 0
        logger.info("Would scan Notion database: %s (requires running Harnext agent)", db_id)
        return items, snippets, count

    def _extract_items(self, raw_findings: list[dict[str, Any]]) -> list[BaseItem]:
        """Extract knowledge items from Notion page data."""
        items: list[BaseItem] = []

        for finding in raw_findings:
            page_id = finding.get("id", "unknown")
            page_id_short = page_id.replace("-", "")[-8:] if len(page_id) > 8 else page_id

            item = KnowledgeItem(
                id=f"nt-{finding.get('object', 'page')}-{page_id_short}",
                source=Source.NOTION,
                source_id=page_id,
                source_url=finding.get("url", ""),
                title=finding.get("title", "Untitled Notion Page"),
                summary=finding.get("summary", "")[:300],
                details=finding.get("content", ""),
                tags=self._infer_notion_tags(finding),
                confidence=Confidence.MEDIUM,
                status=ItemStatus.ACTIVE,
                authors=finding.get("authors", []),
                context=f"Notion page: {finding.get('title', 'Untitled')}",
                references=finding.get("url", ""),
            )
            items.append(item)

        return items

    def _infer_notion_tags(self, finding: dict[str, Any]) -> list[str]:
        """Infer tags from Notion page content and properties."""
        tags: list[str] = ["documentation"]
        title = finding.get("title", "").lower()
        content = finding.get("content", "").lower()

        combined = f"{title} {content}"
        if "architecture" in combined:
            tags.append("architecture")
        if "security" in combined:
            tags.append("security")
        if "api" in combined:
            tags.append("api")
        if "database" in combined or "schema" in combined:
            tags.append("database")
        if "roadmap" in combined or "plan" in combined:
            tags.append("roadmap")
        if "design" in combined:
            tags.append("design")

        return tags
