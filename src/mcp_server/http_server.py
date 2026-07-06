"""
HTTP/SSE MCP Server Transport

Implements the MCP protocol over HTTP with Server-Sent Events for streaming.
Allows remote agents (GitHub Actions, remote Claude instances) to connect
to the knowledge base over TCP.

Supports:
- POST /mcp  — JSON-RPC 2.0 request/response (standard MCP over HTTP)
- GET /health — Health check endpoint
- Bearer token auth via Authorization header

Shares the same KBMCPToolHandler as the stdio server — both transports
access the same coordinator, indexer, and knowledge store.
"""

from __future__ import annotations

import json
import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Optional
from urllib.parse import urlparse

from .activity_logger import get_activity_logger

logger = logging.getLogger(__name__)


class MCPHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler that implements the MCP JSON-RPC protocol.

    Routes:
      POST /mcp     — JSON-RPC 2.0 request
      GET /health   — Health check
    """

    # Class-level references set by the server factory
    tool_handler: Any = None
    auth_token: str = ""
    server_start_time: float = 0.0

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use our logger instead of stderr."""
        logger.debug("HTTP %s", format % args)

    def _check_auth(self) -> bool:
        """Validate Bearer token if auth is configured."""
        if not self.auth_token:
            return True  # No auth configured → dev mode

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == self.auth_token:
                return True

        logger.warning("Auth failed from %s", self.client_address)
        return False

    def _send_json_response(self, data: dict[str, Any], status: int = 200) -> None:
        """Send a JSON response with appropriate headers."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        """Send a JSON error response."""
        self._send_json_response({"error": {"code": code, "message": message}}, status=code)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests (health check only)."""
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._send_json_response({
                "status": "healthy",
                "server": "gymboost-knowledge-base",
                "version": "1.0.0",
                "uptime_seconds": round(time.time() - self.server_start_time, 1),
                "auth_enabled": bool(self.auth_token),
            })
        elif parsed.path == "/":
            self._send_json_response({
                "service": "GymBoost Knowledge Base MCP Server",
                "version": "1.0.0",
                "endpoints": {
                    "mcp": "POST /mcp — JSON-RPC 2.0",
                    "health": "GET /health",
                },
                "auth": "required" if self.auth_token else "disabled",
            })
        else:
            self._send_error(404, f"Not found: {parsed.path}")

    def do_POST(self) -> None:
        """Handle POST requests (MCP JSON-RPC)."""
        parsed = urlparse(self.path)

        if parsed.path != "/mcp":
            self._send_error(404, f"Not found: {parsed.path}")
            return

        # Auth check
        if not self._check_auth():
            self._send_error(401, "Authentication required. Use Authorization: Bearer <token>")
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error(400, "Empty request body")
            return

        try:
            body = self.rfile.read(content_length)
            request = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._send_error(400, f"Invalid JSON: {e}")
            return

        # Process the MCP request
        response = self._handle_mcp_request(request)
        self._send_json_response(response)

    def _handle_mcp_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a single MCP JSON-RPC request. Same logic as stdio server."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._handle_initialize(req_id, params)
        elif method == "initialized":
            # Notification — no response per MCP spec
            return {}
        elif method == "tools/list":
            return self._handle_tools_list(req_id)
        elif method == "tools/call":
            return self._handle_tools_call(req_id, params)
        elif method == "shutdown":
            return self._handle_shutdown(req_id)
        else:
            return self._jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize with auth validation."""
        alog = get_activity_logger()
        alog.log("client_initialize", {"transport": "http", "client": str(self.client_address)})

        return self._jsonrpc_result(req_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "gymboost-knowledge-base",
                "version": "1.0.0",
            },
            "capabilities": {
                "tools": {},
            },
        })

    def _handle_tools_list(self, req_id: Any) -> dict[str, Any]:
        """List available tools."""
        from .tools import TOOL_DEFINITIONS

        tools = [
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
        ]
        return self._jsonrpc_result(req_id, {"tools": tools})

    def _handle_tools_call(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle a tool call."""
        if self.tool_handler is None:
            return self._jsonrpc_error(req_id, -32603, "Tool handler not initialized")

        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            result_text = self.tool_handler.handle(tool_name, arguments)
            return self._jsonrpc_result(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": result_text,
                    }
                ],
            })
        except Exception as e:
            logger.exception("Tool call failed: %s", tool_name)
            return self._jsonrpc_error(req_id, -32603, str(e))

    def _handle_shutdown(self, req_id: Any) -> dict[str, Any]:
        """Handle shutdown (no-op in HTTP mode)."""
        logger.info("Shutdown requested via HTTP")
        return self._jsonrpc_result(req_id, {})

    @staticmethod
    def _jsonrpc_result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


class KBMCPHttpServer:
    """
    HTTP server that serves the MCP protocol over TCP.

    Usage:
        server = KBMCPHttpServer(
            tool_handler=handler,
            host="127.0.0.1",
            port=9020,
            auth_token="my-token",
        )
        server.serve()  # Blocks until SIGTERM
    """

    def __init__(
        self,
        tool_handler: Any,
        host: str = "127.0.0.1",
        port: int = 9020,
        auth_token: str = "",
    ):
        self.host = host
        self.port = port
        self.auth_token = auth_token

        # Inject tool handler into the request handler class
        MCPHTTPRequestHandler.tool_handler = tool_handler
        MCPHTTPRequestHandler.auth_token = auth_token
        MCPHTTPRequestHandler.server_start_time = time.time()

        self._httpd: Optional[HTTPServer] = None

    def serve(self) -> None:
        """Start the HTTP server. Blocks until interrupted."""
        self._httpd = HTTPServer((self.host, self.port), MCPHTTPRequestHandler)

        alog = get_activity_logger()
        alog.log("server_start", {
            "transport": "http",
            "host": self.host,
            "port": self.port,
            "auth_enabled": bool(self.auth_token),
        })

        logger.info("=" * 60)
        logger.info("GymBoost KB MCP Server (HTTP/SSE)")
        logger.info("Listening on http://%s:%d", self.host, self.port)
        logger.info("Auth: %s", "enabled" if self.auth_token else "disabled (dev mode)")
        logger.info("Endpoint: POST http://%s:%d/mcp", self.host, self.port)
        logger.info("Health:   GET  http://%s:%d/health", self.host, self.port)
        logger.info("=" * 60)

        try:
            self._httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down HTTP server...")
            alog.log("server_shutdown", {"transport": "http"})
        finally:
            if self._httpd:
                self._httpd.server_close()

    def shutdown(self) -> None:
        """Gracefully shut down the HTTP server."""
        if self._httpd:
            self._httpd.shutdown()


def create_http_server(
    tool_handler: Any,
    host: str = "127.0.0.1",
    port: int = 9020,
    auth_token: str = "",
) -> KBMCPHttpServer:
    """Factory function to create an HTTP MCP server."""
    return KBMCPHttpServer(
        tool_handler=tool_handler,
        host=host,
        port=port,
        auth_token=auth_token,
    )
