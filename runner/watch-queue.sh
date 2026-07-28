#!/usr/bin/env bash
# Queue watcher for the gymboost self-hosted runner pool.
#
# Polls GitHub every POLL_INTERVAL_SECONDS for queued Actions runs targeting
# our labels vs. currently idle runners, and docker-runs one EPHEMERAL=true
# burst runner per unmet slot (capped at MAX_EXTRA_RUNNERS). Each burst
# runner registers, picks up exactly one job, deregisters, and exits —
# `docker run --rm` then removes the container. True scale-to-zero: no burst
# runners exist when the queue is empty.
#
# Requires ACCESS_TOKEN with Administration:Read (list runners) and
# Actions:Read (list queued runs) at minimum.
set -euo pipefail

REPO="$(echo "${REPO_URL:?REPO_URL not set}" | sed -E 's#https://github.com/##; s#\.git$##')"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-30}"
MAX_EXTRA_RUNNERS="${MAX_EXTRA_RUNNERS:-4}"

export GH_TOKEN="$ACCESS_TOKEN"

log() { printf '[watch-queue] %s\n' "$1"; }

while true; do
  if ! queued="$(gh api "repos/${REPO}/actions/runs?status=queued" --jq '.total_count' 2>&1)"; then
    log "ERROR fetching queued count, skipping this cycle: ${queued}"
    sleep "$POLL_INTERVAL_SECONDS"
    continue
  fi
  if ! idle="$(gh api "repos/${REPO}/actions/runners" \
    --jq '[.runners[] | select(.status == "online" and .busy == false)] | length' 2>&1)"; then
    log "ERROR fetching idle count, skipping this cycle: ${idle}"
    sleep "$POLL_INTERVAL_SECONDS"
    continue
  fi

  needed=$(( queued - idle ))

  if (( needed > 0 )); then
    extra=$(( needed < MAX_EXTRA_RUNNERS ? needed : MAX_EXTRA_RUNNERS ))
    log "queued=${queued} idle=${idle} — starting ${extra} burst runner(s)"
    for _ in $(seq 1 "$extra"); do
      name="gymboost-burst-$(date +%s)-$RANDOM"
      # --network host, not kb-network: a burst runner may also pick up
      # db-smoke.yml, whose `supabase db start` launches sibling Postgres
      # containers via this same socket — those are only reachable at
      # 127.0.0.1:<port> from a runner sharing the host's network namespace.
      # See docker-compose.runner.yml's gh-runner comment for the full story.
      docker run -d --rm \
        --name "$name" \
        --network host \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -e RUNNER_SCOPE=repo \
        -e ACCESS_TOKEN="$ACCESS_TOKEN" \
        -e REPO_URL="$REPO_URL" \
        -e RUNNER_NAME="$name" \
        -e LABELS="$LABELS" \
        -e EPHEMERAL=true \
        -e DISABLE_AUTO_UPDATE=true \
        gymboost-gh-runner:latest >/dev/null
      log "started burst runner ${name}"
    done
  fi

  sleep "$POLL_INTERVAL_SECONDS"
done
