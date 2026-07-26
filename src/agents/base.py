"""
Base Scanner Agent

Abstract base class for all service-specific scanner agents.
Each scanner drives a one-shot harnext query connected to its MCP server.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..config import LLMConfig, ServiceConfig
from ..harnext_query import run_harnext_query
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

    def __init__(
        self,
        service_config: ServiceConfig,
        skill_path: str | None = None,
        llm_config: LLMConfig | None = None,
    ):
        """
        Initialize the scanner agent.

        Args:
            service_config: Service configuration from config.json
            skill_path: Optional path to a skill.md file for this scanner
            llm_config: LLM provider/model settings (from KBConfig.llm)
        """
        self.config = service_config
        self.skill_path = Path(skill_path) if skill_path else None
        self._mcp_def = service_config.mcp_server
        self.llm = llm_config or LLMConfig()

    @property
    def enabled(self) -> bool:
        """Check if this scanner is enabled in config."""
        return self.config.enabled

    def _run_query(self, prompt: str) -> str:
        """
        Run one harnext query synchronously and return the final result text.

        Returns "[]" (empty JSON array) if the harnext SDK isn't installed or
        the query otherwise fails, so callers can uniformly `json.loads()` the
        result without special-casing mock mode.
        """
        system_prompt = (
            self.skill_path.read_text(encoding="utf-8")
            if self.skill_path and self.skill_path.exists()
            else None
        )
        try:
            result_text, _session_id = run_harnext_query(prompt, self.llm, system_prompt=system_prompt)
            return result_text
        except ImportError:
            logger.warning(
                "harnext_sdk not installed. Scanner %s will run in mock mode.",
                self.source.value,
            )
            return "[]"
        except Exception as e:
            logger.error("harnext query failed for %s: %s", self.source.value, e)
            return "[]"

    # Matches a ```json ... ``` (or bare ```) fenced code block.
    _FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)

    @classmethod
    def _parse_json_array(cls, result_text: str) -> list[dict[str, Any]]:
        """
        Parse a query() result as a JSON array of findings (the contract
        each skills/scan-*/skill.md is instructed to follow). Returns []
        on empty/unparseable/non-array output rather than raising, so a bad
        or missing agent response degrades to zero findings, not a crash.

        Tolerates models that don't follow "output ONLY a JSON array" exactly
        — e.g. prose before/after the array, or wrapping it in a markdown
        code fence — by falling back to extracting the array substring
        before giving up.
        """
        if not result_text:
            return []

        for candidate in cls._json_array_candidates(result_text):
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return parsed

        logger.warning("Could not find a JSON array in query result: %.200s", result_text)
        return []

    @classmethod
    def _json_array_candidates(cls, text: str) -> list[str]:
        """Candidate substrings to try parsing as a JSON array, most-likely first."""
        candidates = [text.strip()]

        fenced = cls._FENCED_JSON_RE.search(text)
        if fenced:
            candidates.append(fenced.group(1).strip())

        first, last = text.find("["), text.rfind("]")
        if first != -1 and last != -1 and last > first:
            candidates.append(text[first : last + 1].strip())

        return candidates

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
