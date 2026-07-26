"""
Chat Agent

Provides a conversational Q&A interface over the knowledge base, backed by
a real harnext agent with tool-calling access to the KB's own query tools
(search_kb, get_knowledge, etc. — see the "kb-self" MCP registration in
src/harnext_bootstrap.py). Used by both the `ask_kb` MCP tool and the
`chat` CLI REPL (src/main.py).

Sessions are ephemeral on this app's side: harnext manages session state on
disk (keyed by session_id) via its own resume mechanism, and this module
just passes that session_id back to the caller each turn for them to
resupply on the next one — no conversation state is held here.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import LLMConfig
from .harnext_query import run_harnext_query

logger = logging.getLogger(__name__)

# Tools belonging to the four external scanning services — hard-blocked so
# the chat agent can't incidentally use them just because they're
# registered in the same shared project-scope mcp.json as the KB's own
# query tools (harnext's project mcp.json gives all-or-nothing visibility
# per query; there's no per-agent registration scoping, so this is the
# available mitigation — see src/harnext_bootstrap.py for the trade-off).
_BLOCKED_SERVICE_TOOLS = ["github", "notion", "discord", "telegram"]

DEFAULT_SYSTEM_PROMPT_PATH = Path("chat_system_prompt.md")


class ChatAgent:
    """Conversational Q&A agent over the knowledge base."""

    def __init__(
        self,
        llm_config: LLMConfig,
        system_prompt_path: Path = DEFAULT_SYSTEM_PROMPT_PATH,
    ):
        self.llm_config = llm_config
        self.system_prompt_path = Path(system_prompt_path)
        self._system_prompt = (
            self.system_prompt_path.read_text(encoding="utf-8")
            if self.system_prompt_path.exists()
            else None
        )
        if self._system_prompt is None:
            logger.warning("chat_system_prompt.md not found at %s", self.system_prompt_path)

    def ask(self, prompt: str, session_id: str | None = None) -> tuple[str, str | None]:
        """
        Ask a question, optionally continuing a prior session.

        Returns (answer_text, session_id). Pass the returned session_id back
        in on the next call to continue the same conversation.
        """
        extra_args = {"resume": session_id} if session_id else None
        return run_harnext_query(
            prompt,
            self.llm_config,
            system_prompt=self._system_prompt,
            extra_args=extra_args,
            disallowed_tools=list(_BLOCKED_SERVICE_TOOLS),
        )
