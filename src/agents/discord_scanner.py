"""
Discord Scanner Agent

Scans Discord channels for team discussions, decisions, and announcements.
Extracts memory items from conversations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import LLMConfig, ServiceConfig
from ..storage.models import (
    BaseItem,
    ContextType,
    Decay,
    Importance,
    ItemType,
    MemoryItem,
    ScanResult,
    Source,
)
from .base import BaseScannerAgent

logger = logging.getLogger(__name__)


class DiscordScannerAgent(BaseScannerAgent):
    """Read-only scanner for Discord guilds/channels via MCP."""

    source = Source.DISCORD

    def __init__(
        self,
        service_config: ServiceConfig,
        skill_path: str | None = None,
        llm_config: LLMConfig | None = None,
    ):
        super().__init__(service_config, skill_path, llm_config)
        self.channels = service_config.channels
        self.message_filters = service_config.message_filters

    def scan(self) -> ScanResult:
        return self._safe_scan(self._do_scan)

    def _do_scan(self) -> ScanResult:
        """Execute the full Discord scan."""
        started_at = datetime.now(timezone.utc)
        all_items: list[BaseItem] = []
        all_snippets: list[str] = []
        total_scanned = 0

        # If no channels configured, list all accessible channels
        channels_to_scan = self.channels
        if not channels_to_scan:
            logger.info("No Discord channels configured. Use config.json to specify channels.")
            # In a full implementation, we'd list channels via MCP
            channels_to_scan = []

        for channel in channels_to_scan:
            try:
                items, snippets, count = self._scan_channel(channel)
                all_items.extend(items)
                all_snippets.extend(snippets)
                total_scanned += count
            except Exception as e:
                logger.error("Failed to scan Discord channel %s: %s", channel, e)

        return self._make_scan_result(
            items=all_items,
            raw_snippets=all_snippets,
            started_at=started_at,
            items_scanned=total_scanned,
        )

    def _scan_channel(self, channel: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan messages in a Discord channel via the discord MCP server."""
        since_hours = self.message_filters.get("since_hours", 168)
        max_messages = self.message_filters.get("max_messages_per_channel", 100)
        prompt = (
            f"Read messages in Discord channel #{channel} from the last {since_hours} hours "
            f"(up to {max_messages} messages), including pinned messages and thread replies. "
            "Extract only project-relevant messages (decisions, bugs, feature requests, "
            "architecture discussions, answered questions)."
        )
        result_text = self._run_query(prompt)
        findings = self._parse_json_array(result_text)
        items = self._extract_items(findings)
        return items, [result_text] if result_text else [], len(findings)

    def _extract_items(self, raw_findings: list[dict[str, Any]]) -> list[BaseItem]:
        """Extract memory items from Discord messages."""
        items: list[BaseItem] = []

        for finding in raw_findings:
            message_id = finding.get("id", "unknown")
            message_id_short = message_id[-8:] if len(message_id) > 8 else message_id
            channel_name = finding.get("channel", "unknown")

            item = MemoryItem(
                id=f"dc-{channel_name}-{message_id_short}",
                source=Source.DISCORD,
                source_id=message_id,
                source_url=finding.get("url", ""),
                title=finding.get("summary", "Discord message")[:300],
                context_when_where=f"Discord channel #{channel_name}, {finding.get('timestamp', '')}",
                content=finding.get("content", ""),
                rationale=finding.get("rationale", ""),
                importance=Importance.MEDIUM,
                decay=Decay.WEEKLY,
                participants=finding.get("participants", []),
                context_type=self._infer_context_type(finding),
                scope_decay="Valid until explicitly superseded by a new decision",
                tags=self._infer_discord_tags(finding, channel_name),
            )
            items.append(item)

        return items

    def _infer_context_type(self, finding: dict[str, Any]) -> ContextType:
        """Infer the context type from message content."""
        content = finding.get("content", "").lower()
        if "decision" in content or "decided" in content:
            return ContextType.DECISION
        if "bug" in content or "broken" in content or "error" in content:
            return ContextType.BUG_REPORT
        if "feature" in content or "request" in content:
            return ContextType.FEATURE_REQUEST
        if "question" in content or "?" in content:
            return ContextType.QUESTION
        if "announce" in content or "announcement" in content:
            return ContextType.ANNOUNCEMENT
        return ContextType.DISCUSSION

    def _infer_discord_tags(self, finding: dict[str, Any], channel_name: str) -> list[str]:
        """Infer tags from message content and channel name."""
        tags: list[str] = []
        content = finding.get("content", "").lower()
        combined = f"{channel_name} {content}"

        if "bug" in combined or "fix" in content:
            tags.append("bug")
        if "feature" in combined or "enhancement" in content:
            tags.append("enhancement")
        if "security" in combined:
            tags.append("security")
        if "architecture" in combined or "arch" in content:
            tags.append("architecture")
        if "design" in combined:
            tags.append("design")
        if "api" in combined:
            tags.append("api")
        if "test" in combined:
            tags.append("testing")
        if "deploy" in combined or "release" in content:
            tags.append("devops")
        if "decision" in content or "decided" in content:
            tags.append("decision")

        return tags if tags else ["question"]
