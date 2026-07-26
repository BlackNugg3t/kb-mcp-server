"""
Tests for ChatAgent (src.chat_agent) — conversational Q&A with session
resume, and the tool-visibility mitigation (blocking external service tools).
"""

import harnext_sdk
from harnext_sdk.types import ResultMessage

from src.chat_agent import ChatAgent
from src.config import LLMConfig


def _fake_query_sequence(responses):
    """responses: list of (result_text, session_id) tuples, one per call."""
    state = {"n": 0, "options": []}

    async def fake_query(prompt, options):
        state["options"].append(options)
        result_text, session_id = responses[state["n"]]
        state["n"] += 1
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

    return fake_query, state


def make_agent(tmp_path):
    prompt_path = tmp_path / "chat_system_prompt.md"
    prompt_path.write_text("You are a test assistant.")
    return ChatAgent(LLMConfig(), system_prompt_path=prompt_path)


class TestChatAgent:
    def test_first_turn_has_no_resume(self, monkeypatch, tmp_path):
        fake_query, state = _fake_query_sequence([("answer 1", "sess-1")])
        monkeypatch.setattr(harnext_sdk, "query", fake_query)

        agent = make_agent(tmp_path)
        answer, session_id = agent.ask("hello")

        assert answer == "answer 1"
        assert session_id == "sess-1"
        assert state["options"][0].extra_args == {}

    def test_second_turn_resumes_first_session(self, monkeypatch, tmp_path):
        fake_query, state = _fake_query_sequence([
            ("answer 1", "sess-1"),
            ("answer 2", "sess-1"),
        ])
        monkeypatch.setattr(harnext_sdk, "query", fake_query)

        agent = make_agent(tmp_path)
        _, session_id = agent.ask("hello")
        answer2, session_id2 = agent.ask("follow up", session_id=session_id)

        assert answer2 == "answer 2"
        assert session_id2 == "sess-1"
        # The critical assertion: the second call must resume the session
        # returned by the first, via extra_args={"resume": ...}.
        assert state["options"][1].extra_args == {"resume": "sess-1"}

    def test_blocks_external_service_tools(self, monkeypatch, tmp_path):
        fake_query, state = _fake_query_sequence([("answer", "s1")])
        monkeypatch.setattr(harnext_sdk, "query", fake_query)

        agent = make_agent(tmp_path)
        agent.ask("hello")

        disallowed = state["options"][0].disallowed_tools
        for tool in ("github", "notion", "discord", "telegram"):
            assert tool in disallowed

    def test_system_prompt_loaded_from_file(self, monkeypatch, tmp_path):
        fake_query, state = _fake_query_sequence([("answer", "s1")])
        monkeypatch.setattr(harnext_sdk, "query", fake_query)

        prompt_path = tmp_path / "chat_system_prompt.md"
        prompt_path.write_text("CUSTOM PROMPT TEXT")
        agent = ChatAgent(LLMConfig(), system_prompt_path=prompt_path)
        agent.ask("hello")

        assert state["options"][0].system_prompt == "CUSTOM PROMPT TEXT"

    def test_missing_system_prompt_file_is_none_not_an_error(self, monkeypatch, tmp_path):
        fake_query, state = _fake_query_sequence([("answer", "s1")])
        monkeypatch.setattr(harnext_sdk, "query", fake_query)

        agent = ChatAgent(LLMConfig(), system_prompt_path=tmp_path / "does-not-exist.md")
        answer, _ = agent.ask("hello")

        assert answer == "answer"
        assert state["options"][0].system_prompt is None
