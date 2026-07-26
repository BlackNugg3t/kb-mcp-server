"""
Tests for the shared harnext query helper (src.harnext_query), used by both
the scanner agents and the chat agent.
"""

import harnext_sdk
from harnext_sdk.types import ResultMessage

from src.config import LLMConfig
from src.harnext_query import run_harnext_query


def _fake_query(result_text: str, session_id: str = "sess-1"):
    async def fake_query(prompt, options):
        yield ResultMessage(
            subtype="success",
            is_error=False,
            result=result_text,
            session_id=session_id,
            num_turns=1,
            duration_ms=1.0,
            total_cost_usd=None,
            usage={},
        )

    return fake_query


class TestRunHarnextQuery:
    def test_returns_text_and_session_id(self, monkeypatch):
        monkeypatch.setattr(harnext_sdk, "query", _fake_query("hello", session_id="abc123"))

        text, session_id = run_harnext_query("hi", LLMConfig())

        assert text == "hello"
        assert session_id == "abc123"

    def test_passes_extra_args_disallowed_tools_and_setting_sources(self, monkeypatch):
        captured = {}

        async def fake_query(prompt, options):
            captured["options"] = options
            yield ResultMessage(
                subtype="success",
                is_error=False,
                result="ok",
                session_id="s1",
                num_turns=1,
                duration_ms=1.0,
                total_cost_usd=None,
                usage={},
            )

        monkeypatch.setattr(harnext_sdk, "query", fake_query)

        run_harnext_query(
            "hi",
            LLMConfig(),
            extra_args={"resume": "prev-session"},
            disallowed_tools=["github"],
        )

        options = captured["options"]
        assert options.extra_args == {"resume": "prev-session"}
        assert options.disallowed_tools == ["github"]
        assert options.setting_sources == ["project"]  # default

    def test_setting_sources_override(self, monkeypatch):
        captured = {}

        async def fake_query(prompt, options):
            captured["options"] = options
            yield ResultMessage(
                subtype="success", is_error=False, result="ok", session_id="s1",
                num_turns=1, duration_ms=1.0, total_cost_usd=None, usage={},
            )

        monkeypatch.setattr(harnext_sdk, "query", fake_query)

        run_harnext_query("hi", LLMConfig(), setting_sources=["user"])

        assert captured["options"].setting_sources == ["user"]
