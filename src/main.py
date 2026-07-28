#!/usr/bin/env python3
"""
GymBoost Knowledge Base MCP Server — Main Entry Point

Usage:
    python -m src.main serve     — Start the MCP server (stdio mode)
    python -m src.main scan      — Run a single scan cycle and exit
    python -m src.main scan-loop — Run continuous scan loop (for cron/systemd timer)
    python -m src.main export --output kb-export.json  — Export the KB to a bundle file
    python -m src.main import kb-export.json [--replace]  — Import a bundle file

Environment:
    KB_GITHUB_TOKEN      — GitHub personal access token
    NOTION_API_KEY       — Notion integration token
    DISCORD_BOT_TOKEN    — Discord bot token
    TELEGRAM_BOT_TOKEN   — Telegram bot token
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Configure logging for the application."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
    )


def cmd_serve(config_path: str, transport_override: str | None = None) -> None:
    """Start the MCP server — stdio or HTTP/SSE mode based on config (or --transport)."""
    from src.chat_agent import ChatAgent
    from src.config import load_config
    from src.coordinator import Coordinator
    from src.mcp_server.server import KBMCPToolHandler
    from src.mcp_server.activity_logger import ActivityLogger

    config = load_config(config_path)
    setup_logging(config.logging.level, config.logging.file)

    # Initialize activity logger
    alog = ActivityLogger(config.logging.activity_log_file)

    mode = transport_override or config.mcp_server.mode

    logger = logging.getLogger("kb.main")
    logger.info("Starting GymBoost KB MCP Server v%s", config.version)
    logger.info("Transport mode: %s", mode)
    logger.info("Debug mode: %s", "ON" if config.logging.debug else "OFF")
    logger.info("Activity log: %s", config.logging.activity_log_file)

    if config.logging.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Initialize coordinator for admin tools (rescan_kb, reload_index) —
    # also registers this project's MCP servers with harnext (see
    # src/harnext_bootstrap.py), including the "kb-self" entry ask_kb relies on.
    coordinator = Coordinator(config_path)

    # Chat agent for the ask_kb tool
    chat_agent = ChatAgent(config.llm)

    # Create shared tool handler (same for both transport modes)
    index_path = str(Path(config.storage.base_path) / config.storage.index_file)
    tool_handler = KBMCPToolHandler(
        index_path=index_path,
        coordinator=coordinator,
        chat_agent=chat_agent,
        auth_token=config.mcp_server.auth_token,
        rate_limit_rescan_seconds=config.mcp_server.rate_limit_rescan_seconds,
        rate_limit_import_seconds=config.mcp_server.rate_limit_import_seconds,
    )

    if mode in ("sse", "http") and not config.mcp_server.auth_token:
        raise SystemExit(
            f"Refusing to start: mcp_server.mode={mode!r} exposes the server on "
            f"{config.mcp_server.host}:{config.mcp_server.port} but auth_token is empty "
            "(KB_AUTH_TOKEN unset?). Set a real token or use mode='stdio' for local-only access."
        )

    if mode == "sse" or mode == "http":
        # ── HTTP/SSE mode for remote agents ──────────────────────────
        from src.mcp_server.http_server import create_http_server

        server = create_http_server(
            tool_handler=tool_handler,
            host=config.mcp_server.host,
            port=config.mcp_server.port,
            auth_token=config.mcp_server.auth_token,
        )
        alog.log("server_start", {
            "transport": "http",
            "version": config.version,
            "auth_enabled": bool(config.mcp_server.auth_token),
            "host": config.mcp_server.host,
            "port": config.mcp_server.port,
        })
        server.serve()

    else:
        # ── stdio mode for local agents ──────────────────────────────
        from src.mcp_server.server import KBMCPStdioServer

        server = KBMCPStdioServer(
            tool_handler=tool_handler,
            index_path=index_path,
            coordinator=coordinator,
            auth_token=config.mcp_server.auth_token,
            rate_limit_rescan_seconds=config.mcp_server.rate_limit_rescan_seconds,
            rate_limit_import_seconds=config.mcp_server.rate_limit_import_seconds,
        )
        server.serve()


def cmd_scan(config_path: str) -> None:
    """Run a single scan cycle."""
    from src.config import load_config
    from src.coordinator import Coordinator

    config = load_config(config_path)
    setup_logging(config.logging.level, config.logging.file)

    logger = logging.getLogger("kb.main")
    logger.info("Starting single scan cycle...")

    coordinator = Coordinator(config_path)
    summary = coordinator.run_full_scan()

    logger.info("Scan complete. %d new, %d updated.",
                summary["totals"]["new"], summary["totals"]["updated"])


def cmd_scan_loop(config_path: str) -> None:
    """Run scans in a continuous loop (for use with systemd service)."""
    from src.config import load_config
    from src.coordinator import Coordinator

    config = load_config(config_path)
    setup_logging(config.logging.level, config.logging.file)

    logger = logging.getLogger("kb.main")
    logger.info("Starting continuous scan loop (interval: %d min)...",
                config.scan_interval_minutes)

    coordinator = Coordinator(config_path)

    while True:
        try:
            logger.info("--- Scan cycle starting ---")
            summary = coordinator.run_full_scan()
            logger.info("--- Scan cycle complete: %d new, %d updated ---",
                        summary["totals"]["new"], summary["totals"]["updated"])
        except Exception as e:
            logger.exception("Scan cycle failed: %s", e)

        # Sleep with jitter
        jitter = config.scan_jitter_seconds
        sleep_time = (config.scan_interval_minutes * 60) + (time.time() % jitter)
        logger.info("Next scan in %.1f minutes...", sleep_time / 60)
        time.sleep(sleep_time)


def cmd_chat(config_path: str) -> None:
    """Interactive REPL: talk to the knowledge base's chat agent."""
    from src.chat_agent import ChatAgent
    from src.config import load_config
    from src.harnext_bootstrap import bootstrap as bootstrap_harnext

    config = load_config(config_path)
    setup_logging(config.logging.level, config.logging.file)

    # Register this project's MCP servers with harnext (idempotent). `chat`
    # doesn't go through Coordinator, which normally does this, so it must
    # do it itself — otherwise the agent would have no tool access at all.
    bootstrap_harnext(config, config_path=Path(config_path))

    agent = ChatAgent(config.llm)

    print("GymBoost KB chat — ask a question, or type 'exit'/'quit' to leave.")
    session_id: str | None = None
    while True:
        try:
            question = input("kb> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            break

        try:
            answer, session_id = agent.ask(question, session_id=session_id)
        except Exception as e:
            print(f"\n[error] {e}\n")
            continue

        print(f"\n{answer}\n")


def cmd_export(config_path: str, output: str) -> None:
    """Export the knowledge base to a single portable JSON bundle file."""
    import json

    from src.config import load_config
    from src.kb_export import export_bundle
    from src.storage.indexer import Indexer

    config = load_config(config_path)
    setup_logging(config.logging.level, config.logging.file)
    logger = logging.getLogger("kb.main")

    indexer = Indexer(base_path=config.storage.base_path, index_file=config.storage.index_file)
    indexer.load()

    bundle = export_bundle(indexer)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")

    logger.info("Exported %d entries to %s", len(bundle["entries"]), output_path)


def cmd_import(config_path: str, input_file: str, replace: bool = False) -> None:
    """Import a knowledge base bundle file, merging (or replacing) into the current KB."""
    import json

    from src.config import load_config
    from src.kb_export import import_bundle
    from src.storage.indexer import Indexer

    if not input_file:
        raise SystemExit("The 'import' command requires a bundle file path, e.g.: "
                          "python -m src.main import kb-export.json")

    config = load_config(config_path)
    setup_logging(config.logging.level, config.logging.file)
    logger = logging.getLogger("kb.main")

    bundle = json.loads(Path(input_file).read_text(encoding="utf-8"))

    indexer = Indexer(base_path=config.storage.base_path, index_file=config.storage.index_file)
    indexer.load()

    mode = "replace" if replace else "merge"
    summary = import_bundle(indexer, bundle, mode=mode)
    indexer.save()

    logger.info(
        "Import complete (mode=%s): %d added, %d updated, %d unchanged, %d deleted, %d skipped invalid",
        mode, summary["added"], summary["updated"], summary["unchanged"],
        summary["deleted"], summary["skipped_invalid"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GymBoost Knowledge Base MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main serve
  python -m src.main scan
  python -m src.main scan-loop
  python -m src.main chat
  python -m src.main serve --config /path/to/config.json
  python -m src.main export --output kb-export.json
  python -m src.main import kb-export.json --replace
        """,
    )

    parser.add_argument(
        "command",
        choices=["serve", "scan", "scan-loop", "chat", "export", "import"],
        help="Command to execute",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Bundle file to import (for 'import')",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )
    parser.add_argument(
        "--output", "-o",
        default="kb-export.json",
        help="Output file path (for 'export', default: kb-export.json)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="For 'import': also delete local entries absent from the bundle",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default=None,
        help="For 'serve': override mcp_server.mode from config.json",
    )

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args.config, transport_override=args.transport)
    elif args.command == "scan":
        cmd_scan(args.config)
    elif args.command == "scan-loop":
        cmd_scan_loop(args.config)
    elif args.command == "chat":
        cmd_chat(args.config)
    elif args.command == "export":
        cmd_export(args.config, args.output)
    elif args.command == "import":
        cmd_import(args.config, args.input_file, replace=args.replace)


if __name__ == "__main__":
    main()
