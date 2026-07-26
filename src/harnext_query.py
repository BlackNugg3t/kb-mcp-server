"""
Shared harnext_sdk query helper.

Wraps building HarnextAgentOptions and running one query() call. Used by
both the scanner agents (src/agents/base.py) and the chat agent
(src/chat_agent.py) so the asyncio.run/query-loop/ResultMessage-extraction
logic exists in exactly one place.

The `from harnext_sdk import ...` import is kept inside the async function
body (not at module top) so tests can monkeypatch `harnext_sdk.query` as a
module attribute and have it picked up at call time.
"""

from __future__ import annotations

import asyncio
import logging

from .config import LLMConfig

logger = logging.getLogger(__name__)


def run_harnext_query(
    prompt: str,
    llm_config: LLMConfig,
    system_prompt: str | None = None,
    extra_args: dict[str, str | None] | None = None,
    disallowed_tools: list[str] | None = None,
    setting_sources: list[str] | None = None,
) -> tuple[str, str | None]:
    """
    Run one harnext query synchronously and return (result_text, session_id).

    Raises whatever query()/the harnext_sdk import raises — callers decide
    their own fallback behavior (scanners degrade to "[]"; the chat agent
    lets errors surface to its caller).
    """
    return asyncio.run(
        _query_async(prompt, llm_config, system_prompt, extra_args, disallowed_tools, setting_sources)
    )


async def _query_async(
    prompt: str,
    llm_config: LLMConfig,
    system_prompt: str | None,
    extra_args: dict[str, str | None] | None,
    disallowed_tools: list[str] | None,
    setting_sources: list[str] | None,
) -> tuple[str, str | None]:
    from harnext_sdk import (
        AssistantMessage,
        HarnextAgentOptions,
        ResultMessage,
        SystemMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
        query,
    )

    options = HarnextAgentOptions(
        system_prompt=system_prompt,
        permission_mode=llm_config.permission_mode,
        max_turns=llm_config.max_turns,
        provider=llm_config.provider,
        model=llm_config.model,
        fallback_model=llm_config.fallback_model or None,
        disallowed_tools=disallowed_tools or [],
        # Picks up harnext's project-scope mcp.json registrations (written by
        # src/harnext_bootstrap.py) unless the caller overrides.
        setting_sources=setting_sources if setting_sources is not None else ["project"],
        extra_args=extra_args or {},
    )

    result_text = ""
    session_id: str | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, SystemMessage):
            logger.debug("harnext session started (%s): tools=%s", message.subtype,
                         message.data.get("tools") if message.data else None)

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ThinkingBlock):
                    logger.debug("harnext thinking: %.500s", block.thinking)
                elif isinstance(block, TextBlock):
                    logger.debug("harnext assistant text: %.500s", block.text)
                elif isinstance(block, ToolUseBlock):
                    logger.info("harnext tool call: %s(%s)", block.name, block.input)

        elif isinstance(message, UserMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    logger.debug("harnext tool result (error=%s): %.300s",
                                block.is_error, block.content)

        elif isinstance(message, ResultMessage):
            session_id = message.session_id or session_id
            if message.result:
                result_text = message.result

    return result_text, session_id
