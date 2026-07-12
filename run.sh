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

$DOCKER compose -f docker-compose.runner.yml up -d

echo
echo "Started gh-runner. Useful checks:"
echo "  Runner logs:    docker logs -f gh-runner   (look for 'Listening for Jobs')"
echo "  Registered as:  GitHub repo -> Settings -> Actions -> Runners"
echo
echo "KB is not started — run ./run-kb.sh when you're ready to bring it up."
