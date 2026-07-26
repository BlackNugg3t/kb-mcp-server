"""
Tests for the stdio MCP server transport (src.mcp_server.server).

Exercises KBMCPStdioServer's JSON-RPC request handling directly (no real
stdin/stdout loop needed), covering the auth-enforcement fix and the general
initialize -> tools/list -> tools/call lifecycle.
"""

import json

import pytest

from src.mcp_server.server import KBMCPStdioServer, KBMCPToolHandler
from src.mcp_server.tools import set_chat_agent


def make_server(
    tmp_path,
    auth_token: str = "",
    rate_limit_rescan_seconds: int = 300,
    rate_limit_import_seconds: int = 300,
    chat_agent=None,
):
    handler = KBMCPToolHandler(
        index_path=str(tmp_path / "index.json"),
        auth_token=auth_token,
        rate_limit_rescan_seconds=rate_limit_rescan_seconds,
        rate_limit_import_seconds=rate_limit_import_seconds,
        chat_agent=chat_agent,
    )
    return KBMCPStdioServer(
        tool_handler=handler,
        index_path=str(tmp_path / "index.json"),
        auth_token=auth_token,
        rate_limit_rescan_seconds=rate_limit_rescan_seconds,
        rate_limit_import_seconds=rate_limit_import_seconds,
    )


class FakeChatAgent:
    """Records calls; used to test ask_kb wiring without a real harnext query."""

    def __init__(self, answer: str = "fake answer", session_id: str = "sess-x"):
        self.answer = answer
        self.session_id = session_id
        self.calls: list[tuple[str, str | None]] = []

    def ask(self, prompt: str, session_id: str | None = None):
        self.calls.append((prompt, session_id))
        return self.answer, self.session_id


class TestInitializeAuth:
    """Covers the auth-bypass fix: initialize must actually validate the token."""

    def test_no_auth_configured_always_succeeds(self, tmp_path):
        server = make_server(tmp_path, auth_token="")
        resp = server._handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        assert "result" in resp
        assert server._initialized is True

    def test_correct_token_succeeds(self, tmp_path):
        server = make_server(tmp_path, auth_token="secret")
        resp = server._handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"auth_token": "secret"}}
        )
        assert "result" in resp
        assert server._initialized is True

    def test_wrong_token_rejected(self, tmp_path):
        server = make_server(tmp_path, auth_token="secret")
        resp = server._handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"auth_token": "wrong"}}
        )
        assert "error" in resp
        assert resp["error"]["code"] == -32001
        assert server._initialized is False

    def test_missing_token_rejected(self, tmp_path):
        server = make_server(tmp_path, auth_token="secret")
        resp = server._handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        assert "error" in resp
        assert server._initialized is False


class TestToolCallGating:
    """Tool calls must not succeed before a valid initialize."""

    def test_tools_call_before_initialize_rejected(self, tmp_path):
        server = make_server(tmp_path, auth_token="")  # even with no auth configured
        resp = server._handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "list_tags", "arguments": {}},
            }
        )
        assert "error" in resp
        assert resp["error"]["code"] == -32001

    def test_tools_list_before_initialize_rejected(self, tmp_path):
        server = make_server(tmp_path, auth_token="")
        resp = server._handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert "error" in resp

    def test_tools_list_after_initialize_succeeds(self, tmp_path):
        server = make_server(tmp_path, auth_token="")
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = server._handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert "result" in resp
        tool_names = {t["name"] for t in resp["result"]["tools"]}
        assert "search_kb" in tool_names
        assert "rescan_kb" in tool_names

    def test_tools_call_after_initialize_succeeds(self, tmp_path):
        server = make_server(tmp_path, auth_token="")
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = server._handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "list_tags", "arguments": {}},
            }
        )
        assert "result" in resp
        assert "content" in resp["result"]


class TestDispatchAndRateLimit:
    def test_unknown_method(self, tmp_path):
        server = make_server(tmp_path, auth_token="")
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = server._handle_request({"jsonrpc": "2.0", "id": 2, "method": "bogus/method"})
        assert resp["error"]["code"] == -32601

    def test_rescan_kb_rate_limited_on_second_call(self, tmp_path):
        server = make_server(tmp_path, auth_token="", rate_limit_rescan_seconds=300)
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "rescan_kb", "arguments": {}},
        }
        first = server._handle_request(call)
        second = server._handle_request({**call, "id": 3})

        first_text = first["result"]["content"][0]["text"]
        second_text = second["result"]["content"][0]["text"]
        assert json.loads(second_text).get("status") == "rate_limited"
        # First call may itself report "unavailable" (no coordinator wired) but must not be rate-limited.
        assert json.loads(first_text).get("status") != "rate_limited"


class TestAskKbTool:
    def test_ask_kb_returns_answer_and_session(self, tmp_path):
        chat_agent = FakeChatAgent(answer="42", session_id="sess-1")
        server = make_server(tmp_path, auth_token="", chat_agent=chat_agent)
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        resp = server._handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "ask_kb", "arguments": {"question": "what is the answer?"}},
        })

        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["answer"] == "42"
        assert data["session_id"] == "sess-1"
        assert chat_agent.calls == [("what is the answer?", None)]

    def test_ask_kb_passes_session_id_through(self, tmp_path):
        chat_agent = FakeChatAgent()
        server = make_server(tmp_path, auth_token="", chat_agent=chat_agent)
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        server._handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "ask_kb", "arguments": {"question": "follow up", "session_id": "prev-session"}},
        })

        assert chat_agent.calls == [("follow up", "prev-session")]

    def test_ask_kb_without_chat_agent_reports_unavailable(self, tmp_path):
        set_chat_agent(None)  # reset the module-level global; other tests may have set it
        server = make_server(tmp_path, auth_token="")
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        resp = server._handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "ask_kb", "arguments": {"question": "hi"}},
        })

        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["status"] == "unavailable"


class TestExportImportKbTools:
    def test_export_kb_returns_bundle(self, tmp_path):
        from src.storage.indexer import Indexer
        from src.storage.models import IndexEntry, ItemType, Source

        indexer = Indexer(base_path=tmp_path)
        entry = IndexEntry(
            id="gh-issue-1", type=ItemType.KNOWLEDGE, source=Source.GITHUB,
            source_id="repo#1", path="placeholder.md", title="T", tags=[],
        )
        fp = indexer.make_file_path(entry.id, entry.type)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("hello")
        entry.path = str(fp.relative_to(indexer.base_path))
        entry.content_hash = Indexer.compute_content_hash("hello")
        indexer.add_or_update(entry)
        indexer.save()

        server = make_server(tmp_path, auth_token="")
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = server._handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "export_kb", "arguments": {}},
        })

        bundle = json.loads(resp["result"]["content"][0]["text"])
        assert bundle["format_version"] == 1
        assert len(bundle["entries"]) == 1
        assert bundle["entries"][0]["content"] == "hello"


class TestGetKbStats:
    def test_get_kb_stats_with_real_entries_does_not_crash(self, tmp_path):
        """
        Regression test: get_kb_stats's by_source computation used to iterate
        MasterIndex.scan_stats.keys() (plain strings) and call `.value` on
        them as if they were Source enum members, crashing with
        AttributeError on any KB that had actually been scanned.
        """
        from src.storage.indexer import Indexer
        from src.storage.models import IndexEntry, ItemType, Source

        indexer = Indexer(base_path=tmp_path)
        entry = IndexEntry(
            id="gh-issue-1", type=ItemType.KNOWLEDGE, source=Source.GITHUB,
            source_id="repo#1", path="placeholder.md", title="T", tags=[],
        )
        fp = indexer.make_file_path(entry.id, entry.type)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("hello")
        entry.path = str(fp.relative_to(indexer.base_path))
        entry.content_hash = Indexer.compute_content_hash("hello")
        indexer.add_or_update(entry)
        indexer.update_last_full_scan()
        indexer.save()

        server = make_server(tmp_path, auth_token="")
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = server._handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "get_kb_stats", "arguments": {}},
        })

        data = json.loads(resp["result"]["content"][0]["text"])
        assert "error" not in data
        assert data["total_entries"] == 1
        assert data["by_source"]["github"] == 1
        assert data["by_source"]["notion"] == 0

    def test_import_kb_merges_bundle(self, tmp_path):
        server = make_server(tmp_path, auth_token="")
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        bundle = {
            "format_version": 1,
            "entries": [{
                "entry": {
                    "id": "gh-issue-9", "type": "knowledge", "source": "github",
                    "source_id": "repo#9", "path": "whatever.md", "title": "Imported", "tags": [],
                },
                "content": "imported content",
            }],
        }

        resp = server._handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "import_kb", "arguments": {"bundle_json": json.dumps(bundle)}},
        })

        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["status"] == "completed"
        assert data["added"] == 1

    def test_import_kb_rate_limited_on_second_call(self, tmp_path):
        server = make_server(tmp_path, auth_token="", rate_limit_import_seconds=300)
        server._handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        bundle_json = json.dumps({"format_version": 1, "entries": []})
        call = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "import_kb", "arguments": {"bundle_json": bundle_json}},
        }
        first = server._handle_request(call)
        second = server._handle_request({**call, "id": 3})

        first_data = json.loads(first["result"]["content"][0]["text"])
        second_data = json.loads(second["result"]["content"][0]["text"])
        assert first_data["status"] == "completed"
        assert second_data.get("status") == "rate_limited"
