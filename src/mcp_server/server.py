"""
Knowledge Base MCP Server

Implements a Model Context Protocol server that exposes the GymBoost
knowledge base to external coding agents via stdio JSON-RPC.

Tools exposed: search_kb, get_knowledge, list_tags, list_sources, get_kb_stats
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from .tools import (
    TOOL_DEFINITIONS,
    get_kb_stats,
    get_knowledge,
    list_sources,
    list_tags,
    search_kb,
)

logger = logging.getLogger(__name__)


class KBMCPToolHandler:
    """Handles MCP tool invocations by dispatching to the appropriate function."""

    def __init__(self, index_path: str):
        self.index_path = index_path
        self._handlers: dict[str, Callable] = {
            "search_kb": self._handle_search_kb,
            "get_knowledge": self._handle_get_knowledge,
            "list_tags": self._handle_list_tags,
            "list_sources": self._handle_list_sources,
            "get_kb_stats": self._handle_get_kb_stats,
        }

    def handle(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Dispatch a tool call to the appropriate handler."""
        handler = self._handlers.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            return handler(arguments)
        except Exception as e:
            logger.exception("Tool handler failed for %s", tool_name)
            return json.dumps({"error": str(e)})

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


class KBMCPStdioServer:
    """
    Minimal MCP server implementation over stdio (JSON-RPC 2.0).

    Implements the MCP lifecycle:
    - initialize
    - tools/list
    - tools/call
    - shutdown
    """

    def __init__(self, tool_handler: KBMCPToolHandler | None = None, index_path: str = "knowledge/index.json"):
        self.tool_handler = tool_handler or KBMCPToolHandler(index_path)
        self.index_path = index_path
        self._initialized = False
        self._server_info = {
            "name": "gymboost-knowledge-base",
            "version": "1.0.0",
        }

    def serve(self) -> None:
        """
        Start the MCP server on stdio.
        Reads JSON-RPC requests from stdin, writes responses to stdout.
        """
        logger.info("GymBoost KB MCP Server starting on stdio...")
        logger.info("Index path: %s", self.index_path)

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

    def _handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._handle_initialize(req_id, params)
        elif method == "initialized":
            return None  # Notification, no response
        elif method == "tools/list":
            return self._handle_tools_list(req_id)
        elif method == "tools/call":
            return self._handle_tools_call(req_id, params)
        elif method == "shutdown":
            return self._handle_shutdown(req_id)
        else:
            return self._error_response(req_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the initialize request."""
        self._initialized = True
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


def create_mcp_server(index_path: str = "knowledge/index.json") -> KBMCPStdioServer:
    """Factory function to create a ready-to-serve MCP server."""
    handler = KBMCPToolHandler(index_path)
    return KBMCPStdioServer(tool_handler=handler, index_path=index_path)
