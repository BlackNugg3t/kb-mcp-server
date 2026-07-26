"""
GitHub Scanner Agent

Scans GitHub repositories for issues, pull requests, commits, and discussions.
Extracts knowledge items related to bugs, features, architectural decisions, etc.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import LLMConfig, ServiceConfig
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

    def __init__(
        self,
        service_config: ServiceConfig,
        skill_path: str | None = None,
        llm_config: LLMConfig | None = None,
    ):
        super().__init__(service_config, skill_path, llm_config)
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

        for repo in self.repos:
            logger.info("Scanning GitHub repo: %s", repo)

            if "issues" in self.scan_types:
                try:
                    items, snippets, count = self._scan_issues(repo)
                    all_items.extend(items)
                    all_snippets.extend(snippets)
                    total_scanned += count
                except Exception as e:
                    logger.error("Failed to scan issues for %s: %s", repo, e)

            if "pull_requests" in self.scan_types:
                try:
                    items, snippets, count = self._scan_pull_requests(repo)
                    all_items.extend(items)
                    all_snippets.extend(snippets)
                    total_scanned += count
                except Exception as e:
                    logger.error("Failed to scan PRs for %s: %s", repo, e)

            if "commits" in self.scan_types:
                try:
                    items, snippets, count = self._scan_commits(repo)
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

    def _scan_issues(self, repo: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan GitHub issues for a repo via the github MCP server."""
        filters = self.filters.get("issues", {})
        prompt = (
            f'List GitHub issues for {repo} with state="{filters.get("state", "all")}" '
            f'updated in the last {filters.get("since_days", 7)} days'
        )
        if filters.get("labels"):
            prompt += f", filtered to labels: {', '.join(filters['labels'])}"
        prompt += '. Only include findings with "type": "issue".'

        result_text = self._run_query(prompt)
        findings = [f for f in self._parse_json_array(result_text) if f.get("type") == "issue"]
        items = self._extract_items(findings)
        return items, [result_text] if result_text else [], len(findings)

    def _scan_pull_requests(self, repo: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan pull requests for a repo via the github MCP server."""
        filters = self.filters.get("pull_requests", {})
        prompt = (
            f'List GitHub pull requests for {repo} with state="{filters.get("state", "all")}" '
            f'updated in the last {filters.get("since_days", 7)} days. '
            'Only include findings with "type": "pull_request".'
        )
        result_text = self._run_query(prompt)
        findings = [f for f in self._parse_json_array(result_text) if f.get("type") == "pull_request"]
        items = self._extract_items(findings)
        return items, [result_text] if result_text else [], len(findings)

    def _scan_commits(self, repo: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan recent commits for a repo via the github MCP server."""
        filters = self.filters.get("commits", {})
        prompt = (
            f'List commits for {repo} on branch "{filters.get("branch", "main")}" '
            f'from the last {filters.get("since_days", 7)} days. '
            'Only include findings with "type": "commit".'
        )
        result_text = self._run_query(prompt)
        findings = [f for f in self._parse_json_array(result_text) if f.get("type") == "commit"]
        items = self._extract_items(findings)
        return items, [result_text] if result_text else [], len(findings)

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
