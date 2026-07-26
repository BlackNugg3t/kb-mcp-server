"""
Telegram Scanner Agent

Scans Telegram chats for team coordination messages and decisions.
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


class TelegramScannerAgent(BaseScannerAgent):
    """Read-only scanner for Telegram chats via MCP."""

    source = Source.TELEGRAM

    def __init__(
        self,
        service_config: ServiceConfig,
        skill_path: str | None = None,
        llm_config: LLMConfig | None = None,
    ):
        super().__init__(service_config, skill_path, llm_config)
        self.chats = service_config.chats
        self.message_filters = service_config.message_filters

    def scan(self) -> ScanResult:
        return self._safe_scan(self._do_scan)

    def _do_scan(self) -> ScanResult:
        """Execute the full Telegram scan."""
        started_at = datetime.now(timezone.utc)
        all_items: list[BaseItem] = []
        all_snippets: list[str] = []
        total_scanned = 0

        chats_to_scan = self.chats
        if not chats_to_scan:
            logger.info("No Telegram chats configured. Use config.json to specify chat IDs.")
            chats_to_scan = []

        for chat_id in chats_to_scan:
            try:
                items, snippets, count = self._scan_chat(chat_id)
                all_items.extend(items)
                all_snippets.extend(snippets)
                total_scanned += count
            except Exception as e:
                logger.error("Failed to scan Telegram chat %s: %s", chat_id, e)

        return self._make_scan_result(
            items=all_items,
            raw_snippets=all_snippets,
            started_at=started_at,
            items_scanned=total_scanned,
        )

    def _scan_chat(self, chat_id: str) -> tuple[list[BaseItem], list[str], int]:
        """Scan messages in a Telegram chat via the telegram MCP server."""
        since_hours = self.message_filters.get("since_hours", 168)
        max_messages = self.message_filters.get("max_messages_per_chat", 100)
        prompt = (
            f"Read messages in Telegram chat {chat_id} from the last {since_hours} hours "
            f"(up to {max_messages} messages), including reply chains. "
            "Extract only project-relevant messages (decisions, bugs, feature requests, "
            "architecture discussions, answered questions)."
        )
        result_text = self._run_query(prompt)
        findings = self._parse_json_array(result_text)
        items = self._extract_items(findings)
        return items, [result_text] if result_text else [], len(findings)

    def _extract_items(self, raw_findings: list[dict[str, Any]]) -> list[BaseItem]:
        """Extract memory items from Telegram messages."""
        items: list[BaseItem] = []

        for finding in raw_findings:
            message_id = finding.get("message_id", "unknown")
            chat_name = finding.get("chat", "unknown")

            item = MemoryItem(
                id=f"tg-{chat_name}-{str(message_id)[-8:]}",
                source=Source.TELEGRAM,
                source_id=str(message_id),
                title=finding.get("summary", "Telegram message")[:300],
                context_when_where=f"Telegram chat '{chat_name}', {finding.get('timestamp', '')}",
                content=finding.get("content", ""),
                rationale=finding.get("rationale", ""),
                importance=Importance.MEDIUM,
                decay=Decay.WEEKLY,
                participants=finding.get("participants", []),
                context_type=self._infer_context_type(finding),
                scope_decay="Valid until explicitly superseded by a new decision",
                tags=self._infer_telegram_tags(finding, chat_name),
            )
            items.append(item)

        return items

    def _infer_context_type(self, finding: dict[str, Any]) -> ContextType:
        """Infer context type from message content."""
        content = finding.get("content", "").lower()
        if "decision" in content or "decided" in content:
            return ContextType.DECISION
        if "bug" in content or "broken" in content:
            return ContextType.BUG_REPORT
        if "feature" in content:
            return ContextType.FEATURE_REQUEST
        if "question" in content or "?" in content:
            return ContextType.QUESTION
        return ContextType.DISCUSSION

    def _infer_telegram_tags(self, finding: dict[str, Any], chat_name: str) -> list[str]:
        """Infer tags from message content."""
        tags: list[str] = []
        content = finding.get("content", "").lower()
        combined = f"{chat_name} {content}"

        if "bug" in combined or "fix" in content:
            tags.append("bug")
        if "feature" in combined:
            tags.append("enhancement")
        if "security" in combined:
            tags.append("security")
        if "architecture" in combined:
            tags.append("architecture")
        if "design" in combined:
            tags.append("design")
        if "deploy" in combined:
            tags.append("devops")
        if "decision" in content:
            tags.append("decision")

        return tags if tags else ["question"]
