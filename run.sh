#!/usr/bin/env bash
# Starts the self-hosted GitHub Actions runner ONLY. The KB is a separate
# concern with its own lifecycle — see ./run-kb.sh for that, brought up
# later whenever the KB is actually needed.
#
# No systemd unit involved — `restart: unless-stopped` plus Docker's own
# service handle reboots.
#
# Usage: ./run.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

DOCKER="docker"
if ! docker info &>/dev/null; then
  DOCKER="sudo docker"
fi

# --build is load-bearing, not belt-and-braces: watch-queue.sh is COPYed into
# the image at build time (runner/Dockerfile:24), NOT bind-mounted. Without it,
# a `git pull` that changes watch-queue.sh leaves the OLD script running and
# `up -d` finds nothing to recreate, so the update silently does nothing.
$DOCKER compose -f docker-compose.runner.yml up -d --build

echo
echo "Started gh-runner. Useful checks:"
echo "  Full diagnosis: ./status.sh"
echo "  Runner logs:    docker logs -f gh-runner   (look for 'Listening for Jobs')"
echo "  Registered as:  GitHub repo -> Settings -> Actions -> Runners"
echo
echo "KB is not started — run ./run-kb.sh when you're ready to bring it up."
