#!/usr/bin/env bash
# Starts the KB server. Separate script/lifecycle from ./run.sh (the
# runner) on purpose — bring this up whenever the KB is actually needed.
#
# By default this ONLY starts mcp-server (query mode — search_kb,
# get_knowledge, etc. against whatever's already indexed). It does NOT
# start continuous scanning: the scanner service runs a full scan
# immediately on launch (before its first sleep), so it's opt-in.
#
# Usage:
#   ./run-kb.sh            # mcp-server only (safe, no auto-fill)
#   ./run-kb.sh --scan      # also starts the continuous scanner
#
# For a single one-off fill instead of continuous scanning:
#   docker compose run --rm scanner-once
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

DOCKER="docker"
if ! docker info &>/dev/null; then
  DOCKER="sudo docker"
fi

if [[ "${1:-}" == "--scan" ]]; then
  $DOCKER compose --profile kb-scan up -d mcp-server scanner
  echo "Started mcp-server + scanner (continuous scan-loop is now running)."
else
  $DOCKER compose up -d mcp-server
  echo "Started mcp-server only — knowledge/ stays as-is until you scan."
  echo "  One-off fill:        docker compose run --rm scanner-once"
  echo "  Continuous scanning: ./run-kb.sh --scan"
fi

echo
echo "  KB health: curl http://localhost:9020/health"
