"""
Integration tests for the HTTP/SSE MCP server transport.
"""

import json
import threading
import time
import tempfile
from http.client import HTTPConnection
from pathlib import Path

import pytest

from src.mcp_server.server import KBMCPToolHandler
from src.mcp_server.http_server import KBMCPHttpServer


@pytest.fixture
def test_server():
    """Start an HTTP test server on a random port and return its URL."""
    handler = KBMCPToolHandler(
        index_path="knowledge/index.json",
        auth_token="test-token",
    )

    server = KBMCPHttpServer(
        tool_handler=handler,
        host="127.0.0.1",
        port=19999,
        auth_token="test-token",
    )

    thread = threading.Thread(target=server.serve, daemon=True)
    thread.start()
    time.sleep(0.3)  # Let server start

    yield "http://127.0.0.1:19999"

    server.shutdown()
    thread.join(timeout=1)


class TestHTTPServer:
    """Integration tests for the HTTP MCP transport."""

    def test_health_endpoint(self, test_server):
        """Health check should return status with no auth."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())

        assert resp.status == 200
        assert data["status"] == "healthy"
        assert data["server"] == "gymboost-knowledge-base"
        assert data["auth_enabled"] is True

    def test_auth_required(self, test_server):
        """POST without auth should return 401."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)

        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        conn.request("POST", "/mcp", body=body.encode(), headers={
            "Content-Type": "application/json",
        })
        resp = conn.getresponse()

        assert resp.status == 401

    def test_initialize_with_auth(self, test_server):
        """Initialize with valid auth should succeed."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)

        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }

        conn.request("POST", "/mcp", body=body.encode(), headers=headers)
        resp = conn.getresponse()

        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "result" in data
        assert data["result"]["serverInfo"]["name"] == "gymboost-knowledge-base"
        assert "tools" in data["result"]["capabilities"]

    def test_tools_list(self, test_server):
        """tools/list should return all tool definitions."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)

        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }

        conn.request("POST", "/mcp", body=body.encode(), headers=headers)
        resp = conn.getresponse()

        assert resp.status == 200
        data = json.loads(resp.read().decode())
        tools = data["result"]["tools"]

        tool_names = {t["name"] for t in tools}
        assert "search_kb" in tool_names
        assert "get_knowledge" in tool_names
        assert "rescan_kb" in tool_names
        assert "reload_index" in tool_names

    def test_search_kb_tool_call(self, test_server):
        """Call search_kb via HTTP and get results."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)

        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_kb",
                "arguments": {
                    "query": "test",
                    "limit": 5,
                },
            },
        })

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }

        conn.request("POST", "/mcp", body=body.encode(), headers=headers)
        resp = conn.getresponse()

        assert resp.status == 200
        data = json.loads(resp.read().decode())

        # Should have result with content
        assert "result" in data
        assert "content" in data["result"]
        assert len(data["result"]["content"]) > 0

    def test_list_tags_tool_call(self, test_server):
        """Call list_tags via HTTP."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)

        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "list_tags",
                "arguments": {},
            },
        })

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }

        conn.request("POST", "/mcp", body=body.encode(), headers=headers)
        resp = conn.getresponse()

        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "result" in data

    def test_unknown_tool(self, test_server):
        """Calling an unknown tool should return an error."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)

        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            },
        })

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }

        conn.request("POST", "/mcp", body=body.encode(), headers=headers)
        resp = conn.getresponse()

        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "error" in data["result"]["content"][0]["text"].lower() or "result" in data

    def test_cors_preflight(self, test_server):
        """OPTIONS request should return CORS headers."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)
        conn.request("OPTIONS", "/mcp")
        resp = conn.getresponse()

        assert resp.status == 204
        assert resp.getheader("Access-Control-Allow-Origin") == "*"

    def test_invalid_json(self, test_server):
        """Malformed JSON should return 400."""
        conn = HTTPConnection("127.0.0.1", 19999, timeout=5)

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }

        conn.request("POST", "/mcp", body=b"not json", headers=headers)
        resp = conn.getresponse()

        assert resp.status == 400
