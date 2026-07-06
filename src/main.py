#!/usr/bin/env python3
"""
GymBoost Knowledge Base MCP Server — Main Entry Point

Usage:
    python -m src.main serve     — Start the MCP server (stdio mode)
    python -m src.main scan      — Run a single scan cycle and exit
    python -m src.main scan-loop — Run continuous scan loop (for cron/systemd timer)

Environment:
    GITHUB_TOKEN         — GitHub personal access token
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


def cmd_serve(config_path: str) -> None:
    """Start the MCP server — stdio or HTTP/SSE mode based on config."""
    from src.config import load_config
    from src.coordinator import Coordinator
    from src.mcp_server.server import KBMCPToolHandler
    from src.mcp_server.activity_logger import ActivityLogger

    config = load_config(config_path)
    setup_logging(config.logging.level, config.logging.file)

    # Initialize activity logger
    alog = ActivityLogger(config.logging.activity_log_file)

    logger = logging.getLogger("kb.main")
    logger.info("Starting GymBoost KB MCP Server v%s", config.version)
    logger.info("Transport mode: %s", config.mcp_server.mode)
    logger.info("Debug mode: %s", "ON" if config.logging.debug else "OFF")
    logger.info("Activity log: %s", config.logging.activity_log_file)

    if config.logging.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Initialize coordinator for admin tools (rescan_kb, reload_index)
    coordinator = Coordinator(config_path)

    # Create shared tool handler (same for both transport modes)
    index_path = str(Path(config.storage.base_path) / config.storage.index_file)
    tool_handler = KBMCPToolHandler(
        index_path=index_path,
        coordinator=coordinator,
        auth_token=config.mcp_server.auth_token,
        rate_limit_rescan_seconds=config.mcp_server.rate_limit_rescan_seconds,
    )

    mode = config.mcp_server.mode

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GymBoost Knowledge Base MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main serve
  python -m src.main scan
  python -m src.main scan-loop
  python -m src.main serve --config /path/to/config.json
        """,
    )

    parser.add_argument(
        "command",
        choices=["serve", "scan", "scan-loop"],
        help="Command to execute",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args.config)
    elif args.command == "scan":
        cmd_scan(args.config)
    elif args.command == "scan-loop":
        cmd_scan_loop(args.config)


if __name__ == "__main__":
    main()
