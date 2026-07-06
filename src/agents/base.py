"""
Base Scanner Agent

Abstract base class for all service-specific scanner agents.
Each scanner is a read-only Harnext instance connected to its MCP server.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..config import MCPServiceDef, ServiceConfig
from ..storage.models import (
    BaseItem,
    ItemType,
    ScanResult,
    Source,
)

logger = logging.getLogger(__name__)


class BaseScannerAgent(ABC):
    """
    Abstract base for scanner agents.

    Each scanner:
    - Is READ-ONLY (no write/edit/bash tools)
    - Connects to a single external service via MCP
    - Extracts and classifies items from raw findings
    - Returns a structured ScanResult
    """

    source: Source  # Must be set by subclasses
    item_type: ItemType = ItemType.KNOWLEDGE  # Default, override as needed

    def __init__(self, service_config: ServiceConfig, skill_path: str | None = None):
        """
        Initialize the scanner agent.

        Args:
            service_config: Service configuration from config.json
            skill_path: Optional path to a skill.md file for this scanner
        """
        self.config = service_config
        self.skill_path = Path(skill_path) if skill_path else None
        self._mcp_def = service_config.mcp_server
        self._agent: Any = None  # Harnext instance, initialized lazily

    @property
    def enabled(self) -> bool:
        """Check if this scanner is enabled in config."""
        return self.config.enabled

    def _get_harnext_kwargs(self) -> dict[str, Any]:
        """
        Build the kwargs dict for initializing a Harnext agent.
        Subclasses can override to customize.
        """
        kwargs: dict[str, Any] = {
            "tools": ["read", "skill", "mcp"],
            "permission_mode": "auto",
            "max_turns": 20,
        }

        # Add MCP server definition
        if self._mcp_def.command:
            kwargs["mcp_servers"] = {
                self.source.value: {
                    "command": self._mcp_def.command,
                    "args": self._mcp_def.args,
                    "env": self._mcp_def.env,
                    "mode": self._mcp_def.mode,
                    "allow": self._mcp_def.allow,
                }
            }
        elif self._mcp_def.url:
            kwargs["mcp_servers"] = {
                self.source.value: {
                    "url": self._mcp_def.url,
                    "mode": self._mcp_def.mode,
                    "allow": self._mcp_def.allow,
                }
            }

        return kwargs

    def _init_agent(self) -> Any:
        """
        Initialize the Harnext agent for this scanner.
        Uses lazy init to avoid creating agents for disabled services.
        """
        if self._agent is not None:
            return self._agent

        try:
            from harnext import Harnext

            kwargs = self._get_harnext_kwargs()
            self._agent = Harnext(**kwargs)

            # Register skill if available
            if self.skill_path and self.skill_path.exists():
                self._agent.skills.add(str(self.skill_path))

            logger.info("Scanner agent initialized for %s", self.source.value)
            return self._agent
        except ImportError:
            logger.warning(
                "harnext SDK not installed. Scanner %s will run in mock mode.",
                self.source.value,
            )
            return None
        except Exception as e:
            logger.error("Failed to initialize scanner agent for %s: %s", self.source.value, e)
            return None

    @abstractmethod
    def scan(self) -> ScanResult:
        """
        Execute a scan of the external service.

        Returns:
            ScanResult with extracted items and metadata.
        """
        ...

    @abstractmethod
    def _extract_items(self, raw_findings: list[dict[str, Any]]) -> list[BaseItem]:
        """
        Extract and classify knowledge base items from raw findings.

        Args:
            raw_findings: Raw data from the external service

        Returns:
            List of classified BaseItem instances
        """
        ...

    def _make_scan_result(
        self,
        items: list[BaseItem],
        raw_snippets: list[str],
        started_at: datetime,
        items_scanned: int = 0,
        error: Optional[str] = None,
    ) -> ScanResult:
        """Create a ScanResult from extracted items."""
        return ScanResult(
            source=self.source,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            items_scanned=items_scanned,
            items_new=len(items),  # Will be refined by diff engine
            new_items=items,
            raw_snippets=raw_snippets,
            error=error,
        )

    def _safe_scan(self, scan_func) -> ScanResult:
        """
        Wrapper that catches exceptions and returns an error ScanResult.
        """
        started_at = datetime.now(timezone.utc)
        try:
            if not self.enabled:
                return ScanResult(
                    source=self.source,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    error="Service disabled in configuration",
                )
            return scan_func()
        except Exception as e:
            logger.exception("Scan failed for %s", self.source.value)
            return ScanResult(
                source=self.source,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error=str(e),
            )
