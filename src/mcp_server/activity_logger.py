"""
Activity Logger

Provides persistent, structured audit logging of all knowledge base operations:
- MCP tool calls (who queried what, when)
- Scan results (what was found, from which source)
- Admin actions (rescan, reload)
- Error events

Writes JSONL (one JSON object per line) to a configurable log file.
Rotates automatically when file exceeds configured max size.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Max size before rotation (50MB)
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
# Keep this many rotated files
MAX_BACKUPS = 5


class ActivityLogger:
    """
    Singleton activity logger for the knowledge base system.

    Usage:
        alog = ActivityLogger("logs/activity.jsonl")
        alog.log("mcp_query", {"tool": "search_kb", "query": "bug", "results": 5})
        alog.log("scan_complete", {"source": "github", "new": 10, "updated": 3})
    """

    _instance: Optional[ActivityLogger] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> ActivityLogger:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.__initialized = False
        return cls._instance

    def __init__(self, log_path: str = "logs/activity.jsonl", max_bytes: int = DEFAULT_MAX_BYTES):
        if self.__initialized:
            return
        self.__initialized = True

        self.log_path = Path(log_path)
        self.max_bytes = max_bytes
        self._write_lock = threading.Lock()

        # Ensure directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        if not self.log_path.exists():
            return

        if self.log_path.stat().st_size < self.max_bytes:
            return

        # Rotate: activity.jsonl → activity.1.jsonl → activity.2.jsonl ...
        for i in range(MAX_BACKUPS - 1, 0, -1):
            old = self.log_path.parent / f"{self.log_path.stem}.{i}.jsonl"
            new = self.log_path.parent / f"{self.log_path.stem}.{i + 1}.jsonl"
            if old.exists():
                old.rename(new)

        backup = self.log_path.parent / f"{self.log_path.stem}.1.jsonl"
        self.log_path.rename(backup)

    def log(self, event_type: str, data: dict[str, Any], **extra: Any) -> None:
        """
        Write a structured activity event to the log.

        Args:
            event_type: Short event identifier (e.g., 'mcp_query', 'scan_start', 'error')
            data: Dict of event-specific data (will be serialized to JSON)
            **extra: Additional key-value pairs merged into the event
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "pid": os.getpid(),
            **extra,
            **data,
        }

        # Sanitize: remove any 'token' or 'auth' keys to prevent secret leaks
        event = {k: v for k, v in event.items() if not _is_sensitive_key(k)}

        line = json.dumps(event, default=str, ensure_ascii=False) + "\n"

        with self._write_lock:
            self._rotate_if_needed()
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)

    def log_mcp_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result_summary: str,
        duration_ms: float = 0,
        error: Optional[str] = None,
    ) -> None:
        """Log an MCP tool invocation."""
        # Strip index_path from logged args (always the same)
        safe_args = {k: v for k, v in arguments.items() if k != "index_path"}

        self.log(
            "mcp_call",
            {
                "tool": tool_name,
                "args": safe_args,
                "result": result_summary,
                "duration_ms": round(duration_ms, 2),
                "success": error is None,
                "error": error,
            },
        )

    def log_scan_event(
        self,
        event_type: str,
        source: str,
        **data: Any,
    ) -> None:
        """Log a scan-related event."""
        self.log(
            event_type,
            {"source": source, **data},
        )

    def log_error(
        self,
        component: str,
        error_message: str,
        **context: Any,
    ) -> None:
        """Log an error event."""
        self.log(
            "error",
            {"component": component, "error": error_message, **context},
        )

    def recent_events(self, event_type: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        """
        Read recent events from the log (for debugging/diagnostics).

        Args:
            event_type: Optional filter by event type
            limit: Maximum events to return

        Returns:
            List of recent events (newest first)
        """
        if not self.log_path.exists():
            return []

        events: list[dict[str, Any]] = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        if event_type and event.get("type") != event_type:
                            continue
                        events.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning("Failed to read activity log: %s", e)
            return []

        # Return newest first, limited
        return list(reversed(events[-limit:]))

    def clear(self) -> None:
        """Clear the activity log (for testing/reset)."""
        if self.log_path.exists():
            self.log_path.unlink()

    @property
    def size_bytes(self) -> int:
        """Current size of the activity log in bytes."""
        return self.log_path.stat().st_size if self.log_path.exists() else 0

    @property
    def event_count(self) -> int:
        """Approximate number of events in the log."""
        if not self.log_path.exists():
            return 0
        count = 0
        with open(self.log_path, "r", encoding="utf-8") as f:
            for _ in f:
                count += 1
        return count


def _is_sensitive_key(key: str) -> bool:
    """Check if a key name suggests it contains sensitive data."""
    key_lower = key.lower()
    sensitive = {"token", "api_key", "auth", "secret", "password", "credential"}
    return any(s in key_lower for s in sensitive)


# Convenience: global accessor that returns the singleton
def get_activity_logger() -> ActivityLogger:
    """Get or create the singleton ActivityLogger."""
    return ActivityLogger()
