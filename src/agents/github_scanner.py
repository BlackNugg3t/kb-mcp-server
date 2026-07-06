"""
GitHub Scanner Agent

Scans GitHub repositories for issues, pull requests, commits, and discussions.
Extracts knowledge items related to bugs, features, architectural decisions, etc.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import ServiceConfig
from ..storage.models import (
    BaseItem,
    Confidence,
    ItemStatus,
    ItemType,
    KnowledgeItem,
    MemoryItem,
    ScanResult,
    Source,
)
from .base import BaseScannerAgent

logger = logging.getLogger(__name__)


class GitHubScannerAgent(BaseScannerAgent):
    """Read-only scanner for GitHub repositories via MCP."""

    source = Source.GITHUB

    def __init__(self, service_config: ServiceConfig, skill_path: str | None = None):
        super().__init__(service_config, skill_path)
        self.repos = service_config.repos
        self.scan_types = service_config.scan_types or ["issues", "pull_requests", "commits"]
        self.filters = service_config.filters

    def scan(self) -> ScanResult:
        return self._safe_scan(self._do_scan)

    def _do_scan(self) -> ScanResult:
        """Execute the full GitHub scan."""
        started_at = datetime.now(timezone.utc)
        all_items: list[BaseItem] = []
        all_snippets: list[str] = []
        total_scanned = 0

        agent = self._init_agent()

        for repo in self.repos:
            logger.info("Scanning GitHub repo: %s", repo)

            if "issues" in self.scan_types:
                try:
                    items, snippets, count = self._scan_issues(agent, repo)
                    all_items.extend(items)
                    all_snippets.extend(snippets)
                    total_scanned += count
                except Exception as e:
                    logger.error("Failed to scan issues for %s: %s", repo, e)

            if "pull_requests" in self.scan_types:
                try:
                    items, snippets, count = self._scan_pull_requests(agent, repo)
                    all_items.extend(items)
                    all_snippets.extend(snippets)
                    total_scanned += count
                except Exception as e:
                    logger.error("Failed to scan PRs for %s: %s", repo, e)

            if "commits" in self.scan_types:
                try:
                    items, snippets, count = self._scan_commits(agent, repo)
                    all_items.extend(items)
                    all_snippets.extend(snippets)
                    total_scanned += count
                except Exception as e:
                    logger.error("Failed to scan commits for %s: %s", repo, e)

        return self._make_scan_result(
            items=all_items,
            raw_snippets=all_snippets,
            started_at=started_at,
            items_scanned=total_scanned,
        )

    def _scan_issues(self, agent: Any, repo: str) -> tuple[list[BaseItem], list[str], int]:
        """
        Scan GitHub issues for a repo.
        In production, this would use the MCP server's list_issues and get_issue tools.
        """
        items: list[BaseItem] = []
        snippets: list[str] = []
        count = 0

        # In production with Harnext + MCP:
        # result = agent.run(f"List all issues for {repo} ...")
        # Parse the structured output

        # For now, provide the interface that will be used
        logger.info("Would scan issues for %s (requires running Harnext agent)", repo)

        return items, snippets, count

    def _scan_pull_requests(self, agent: Any, repo: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan pull requests for a repo."""
        items: list[BaseItem] = []
        snippets: list[str] = []
        count = 0
        logger.info("Would scan PRs for %s (requires running Harnext agent)", repo)
        return items, snippets, count

    def _scan_commits(self, agent: Any, repo: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan recent commits for a repo."""
        items: list[BaseItem] = []
        snippets: list[str] = []
        count = 0
        logger.info("Would scan commits for %s (requires running Harnext agent)", repo)
        return items, snippets, count

    def _extract_items(self, raw_findings: list[dict[str, Any]]) -> list[BaseItem]:
        """
        Extract knowledge items from raw GitHub API responses.
        Handles issues, PRs, commits, and discussions.
        """
        items: list[BaseItem] = []

        for finding in raw_findings:
            finding_type = finding.get("type", "issue")

            if finding_type == "issue":
                item = KnowledgeItem(
                    id=f"gh-issue-{finding['number']}",
                    source=Source.GITHUB,
                    source_id=f"{finding.get('repo', '')}#{finding['number']}",
                    source_url=finding.get("html_url", ""),
                    title=finding.get("title", "Untitled Issue"),
                    summary=finding.get("body", "")[:300] if finding.get("body") else "",
                    details=finding.get("body", ""),
                    tags=self._infer_tags(finding),
                    confidence=Confidence.HIGH,
                    status=ItemStatus.ACTIVE,
                    authors=[finding.get("user", {}).get("login", "unknown")],
                    context=f"Issue #{finding['number']} in {finding.get('repo', '')}",
                    references=finding.get("html_url", ""),
                )
                items.append(item)

            elif finding_type == "pull_request":
                item = KnowledgeItem(
                    id=f"gh-pr-{finding['number']}",
                    source=Source.GITHUB,
                    source_id=f"{finding.get('repo', '')}#{finding['number']}",
                    source_url=finding.get("html_url", ""),
                    title=finding.get("title", "Untitled PR"),
                    summary=finding.get("body", "")[:300] if finding.get("body") else "",
                    details=finding.get("body", ""),
                    tags=["enhancement"],
                    confidence=Confidence.HIGH,
                    authors=[finding.get("user", {}).get("login", "unknown")],
                    context=f"PR #{finding['number']} in {finding.get('repo', '')}",
                    references=finding.get("html_url", ""),
                )
                items.append(item)

            elif finding_type == "commit":
                item = KnowledgeItem(
                    id=f"gh-commit-{finding.get('sha', 'unknown')[:8]}",
                    source=Source.GITHUB,
                    source_id=finding.get("sha", "unknown")[:8],
                    source_url=finding.get("html_url", ""),
                    title=finding.get("message", "").split("\n")[0][:300] if finding.get("message") else "Untitled Commit",
                    summary=finding.get("message", "")[:300] if finding.get("message") else "",
                    details=finding.get("message", ""),
                    tags=["enhancement"],
                    confidence=Confidence.HIGH,
                    authors=[finding.get("author", {}).get("login", "unknown")],
                    context=f"Commit {finding.get('sha', 'unknown')[:8]} in {finding.get('repo', '')}",
                    references=finding.get("html_url", ""),
                )
                items.append(item)

        return items

    def _infer_tags(self, finding: dict[str, Any]) -> list[str]:
        """Infer tags from GitHub issue labels."""
        tags: list[str] = []
        labels = finding.get("labels", [])
        if isinstance(labels, list):
            for label in labels:
                if isinstance(label, dict):
                    name = label.get("name", "").lower()
                else:
                    name = str(label).lower()
                if name in {
                    "bug", "enhancement", "documentation", "security",
                    "performance", "testing", "devops", "design", "epic",
                    "blocked", "question",
                }:
                    tags.append(name)
        return tags if tags else ["enhancement"]
