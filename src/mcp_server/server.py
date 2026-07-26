"""
Knowledge Base MCP Server

Implements a Model Context Protocol server that exposes the GymBoost
knowledge base to external coding agents via stdio JSON-RPC.

Security features:
- Token-based authentication (AUTH_TOKEN)
- Rate limiting on admin tools (rescan_kb)
- Path traversal protection
- Structured activity audit log

Tools exposed:
  - search_kb, get_knowledge, list_tags, list_sources, get_kb_stats, export_kb  (query)
  - ask_kb (conversational Q&A over the knowledge base)
  - rescan_kb (trigger immediate knowledge refresh from sources)
  - reload_index (reload index from disk)
  - import_kb (restore/merge a knowledge base bundle)
"""

from __future__ import annotations

import json
import logging
import time
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from .tools import (
    TOOL_DEFINITIONS,
    ask_kb,
    export_kb,
    get_kb_stats,
    get_knowledge,
    import_kb,
    list_sources,
    list_tags,
    reload_index,
    rescan_kb,
    search_kb,
    set_chat_agent,
    set_coordinator,
)
from .activity_logger import ActivityLogger, get_activity_logger

logger = logging.getLogger(__name__)

# Admin tools that require rate limiting
ADMIN_TOOLS = {"rescan_kb", "import_kb"}


class KBMCPToolHandler:
    """Handles MCP tool invocations by dispatching to the appropriate function."""

    def __init__(
        self,
        index_path: str,
        coordinator: Any = None,
        chat_agent: Any = None,
        auth_token: str = "",
        rate_limit_rescan_seconds: int = 300,
        rate_limit_import_seconds: int = 300,
    ):
        self.index_path = index_path
        self.auth_token = auth_token
        self.rate_limit_rescan_seconds = rate_limit_rescan_seconds
        self.rate_limit_import_seconds = rate_limit_import_seconds

        # Rate limiting state
        self._last_rescan_time: float = 0.0
        self._last_import_time: float = 0.0

        # Activity logger
        self.activity_log = get_activity_logger()

        # Inject coordinator for admin tools
        if coordinator is not None:
            set_coordinator(coordinator)

        # Inject chat agent for ask_kb
        if chat_agent is not None:
            set_chat_agent(chat_agent)

        self._handlers: dict[str, Callable] = {
            "search_kb": self._handle_search_kb,
            "get_knowledge": self._handle_get_knowledge,
            "list_tags": self._handle_list_tags,
            "list_sources": self._handle_list_sources,
            "get_kb_stats": self._handle_get_kb_stats,
            "export_kb": self._handle_export_kb,
            "ask_kb": self._handle_ask_kb,
            "rescan_kb": self._handle_rescan_kb,
            "reload_index": self._handle_reload_index,
            "import_kb": self._handle_import_kb,
        }

    def _check_rate_limit(self, tool_name: str) -> tuple[bool, str]:
        """Check if a rate-limited tool can be invoked."""
        if tool_name not in ADMIN_TOOLS:
            return True, ""

        if tool_name == "rescan_kb":
            now = time.time()
            elapsed = now - self._last_rescan_time
            if elapsed < self.rate_limit_rescan_seconds:
                wait = int(self.rate_limit_rescan_seconds - elapsed)
                return False, f"Rate limited. Please wait {wait}s before rescanning."
            self._last_rescan_time = now

        elif tool_name == "import_kb":
            now = time.time()
            elapsed = now - self._last_import_time
            if elapsed < self.rate_limit_import_seconds:
                wait = int(self.rate_limit_import_seconds - elapsed)
                return False, f"Rate limited. Please wait {wait}s before importing again."
            self._last_import_time = now

        return True, ""

    def handle(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Dispatch a tool call to the appropriate handler."""
        handler = self._handlers.get(tool_name)
        if handler is None:
            self.activity_log.log_mcp_call(
                tool_name, arguments, "unknown_tool", error="Unknown tool"
            )
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        # Rate limit check for admin tools
        allowed, rate_msg = self._check_rate_limit(tool_name)
        if not allowed:
            self.activity_log.log_mcp_call(
                tool_name, arguments, "rate_limited", error=rate_msg
            )
            return json.dumps({"error": rate_msg, "status": "rate_limited"})

        start = time.time()
        try:
            result = handler(arguments)
            duration = (time.time() - start) * 1000

            # Log successful call
            self._log_tool_result(tool_name, arguments, result, duration)

            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.exception("Tool handler failed for %s", tool_name)

            self.activity_log.log_mcp_call(
                tool_name, arguments, "error",
                duration_ms=duration, error=str(e),
            )
            return json.dumps({"error": str(e)})

    def _log_tool_result(
        self, tool_name: str, args: dict[str, Any], result: str, duration_ms: float
    ) -> None:
        """Extract a summary from the result and log to activity logger."""
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                if "total_results" in parsed:
                    summary = f"{parsed['total_results']} results"
                elif "status" in parsed:
                    summary = parsed["status"]
                elif "error" in parsed:
                    summary = "error"
                else:
                    summary = "ok"
            else:
                summary = "ok"
        except (json.JSONDecodeError, TypeError):
            summary = "ok"

        self.activity_log.log_mcp_call(
            tool_name, args, summary, duration_ms=duration_ms,
        )

    def _handle_search_kb(self, args: dict[str, Any]) -> str:
        return search_kb(
            index_path=self.index_path,
            query=args.get("query", ""),
            tags=args.get("tags"),
            source=args.get("source"),
            item_type=args.get("item_type"),
            limit=args.get("limit", 20),
        )

    def _handle_get_knowledge(self, args: dict[str, Any]) -> str:
        return get_knowledge(
            index_path=self.index_path,
            item_id=args["item_id"],
        )

    def _handle_list_tags(self, args: dict[str, Any]) -> str:
        return list_tags(index_path=self.index_path)

    def _handle_list_sources(self, args: dict[str, Any]) -> str:
        return list_sources(index_path=self.index_path)

    def _handle_get_kb_stats(self, args: dict[str, Any]) -> str:
        return get_kb_stats(index_path=self.index_path)

    def _handle_export_kb(self, args: dict[str, Any]) -> str:
        return export_kb(index_path=self.index_path)

    def _handle_ask_kb(self, args: dict[str, Any]) -> str:
        return ask_kb(
            index_path=self.index_path,
            question=args["question"],
            session_id=args.get("session_id"),
        )

    def _handle_rescan_kb(self, args: dict[str, Any]) -> str:
        return rescan_kb(
            index_path=self.index_path,
            source=args.get("source"),
            force=args.get("force", True),
        )

    def _handle_reload_index(self, args: dict[str, Any]) -> str:
        return reload_index(index_path=self.index_path)

    def _handle_import_kb(self, args: dict[str, Any]) -> str:
        return import_kb(
            index_path=self.index_path,
            bundle_json=args["bundle_json"],
            mode=args.get("mode", "merge"),
        )


class KBMCPStdioServer:
    """
    Minimal MCP server implementation over stdio (JSON-RPC 2.0).

    Implements the MCP lifecycle:
    - initialize (with auth token validation)
    - tools/list
    - tools/call (with rate limiting + activity logging)
    - shutdown
    """

    def __init__(
        self,
        tool_handler: KBMCPToolHandler | None = None,
        index_path: str = "knowledge/index.json",
        coordinator: Any = None,
        auth_token: str = "",
        rate_limit_rescan_seconds: int = 300,
        rate_limit_import_seconds: int = 300,
    ):
        self.tool_handler = tool_handler or KBMCPToolHandler(
            index_path=index_path,
            coordinator=coordinator,
            auth_token=auth_token,
            rate_limit_rescan_seconds=rate_limit_rescan_seconds,
            rate_limit_import_seconds=rate_limit_import_seconds,
        )
        self.index_path = index_path
        self.auth_token = auth_token
        self._initialized = False
        self._server_info = {
            "name": "gymboost-knowledge-base",
            "version": "1.0.0",
        }
        self.activity_log = get_activity_logger()

    def serve(self) -> None:
        """
        Start the MCP server on stdio.
        Reads JSON-RPC requests from stdin, writes responses to stdout.
        """
        logger.info("GymBoost KB MCP Server starting on stdio...")
        logger.info("Index path: %s", self.index_path)
        logger.info("Auth: %s", "enabled" if self.auth_token else "disabled (dev mode)")

        self.activity_log.log("server_start", {
            "index_path": self.index_path,
            "auth_enabled": bool(self.auth_token),
        })

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON: %s", e)
                continue

            response = self._handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

    def _validate_initialize_auth(self, params: dict[str, Any]) -> bool:
        """Validate auth token during initialize if configured."""
        if not self.auth_token:
            return True

        client_token = params.get("auth_token", "")
        return client_token == self.auth_token

    def _handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._handle_initialize(req_id, params)
        elif method == "initialized":
            return None  # Notification, no response
        elif method in ("tools/list", "tools/call") and not self._initialized:
            return self._error_response(req_id, -32001, "Not authenticated: call initialize first")
        elif method == "tools/list":
            return self._handle_tools_list(req_id)
        elif method == "tools/call":
            return self._handle_tools_call(req_id, params)
        elif method == "shutdown":
            return self._handle_shutdown(req_id)
        else:
            return self._error_response(req_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the initialize request with auth validation."""
        if not self._validate_initialize_auth(params):
            logger.warning("Initialize rejected: invalid auth token")
            return self._error_response(req_id, -32001, "Authentication failed")

        self._initialized = True
        logger.info("MCP client initialized successfully")
        self.activity_log.log("client_initialize", {})

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": self._server_info,
                "capabilities": {
                    "tools": {},
                },
            },
        }

    def _handle_tools_list(self, req_id: Any) -> dict[str, Any]:
        """List available tools."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": td["name"],
                        "description": td["description"],
                        "inputSchema": {
                            "type": "object",
                            "properties": td["parameters"]["properties"],
                            "required": td["parameters"].get("required", []),
                        },
                    }
                    for td in TOOL_DEFINITIONS
                ],
            },
        }

    def _handle_tools_call(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle a tool call."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Always inject index_path
        if "index_path" not in arguments:
            arguments["index_path"] = self.index_path

        result_text = self.tool_handler.handle(tool_name, arguments)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result_text,
                    }
                ],
            },
        }

    def _handle_shutdown(self, req_id: Any) -> dict[str, Any]:
        """Handle shutdown request."""
        logger.info("Shutting down MCP server...")
        self.activity_log.log("server_shutdown", {})
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    @staticmethod
    def _error_response(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }


def create_mcp_server(
    index_path: str = "knowledge/index.json",
    coordinator: Any = None,
    auth_token: str = "",
    rate_limit_rescan_seconds: int = 300,
) -> KBMCPStdioServer:
    """Factory function to create a ready-to-serve MCP server."""
    handler = KBMCPToolHandler(
        index_path=index_path,
        coordinator=coordinator,
        auth_token=auth_token,
        rate_limit_rescan_seconds=rate_limit_rescan_seconds,
    )
    return KBMCPStdioServer(
        tool_handler=handler,
        index_path=index_path,
        coordinator=coordinator,
        auth_token=auth_token,
        rate_limit_rescan_seconds=rate_limit_rescan_seconds,
    )
