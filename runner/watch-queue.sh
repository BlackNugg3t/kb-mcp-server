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

  # Count burst runners already alive — registered with GitHub OR still
  # booting/registering. `docker ps` sees both; GitHub's idle/busy list does
  # NOT see a container that hasn't finished registering yet (~15-30s). Without
  # this, each ~30s cycle recomputes `needed` before the previous wave has
  # registered, so it over-provisions past the cap — MAX_EXTRA_RUNNERS was a
  # per-cycle burst limit, never a concurrent ceiling (observed: 11 live burst
  # containers with the cap set to 8). Over-provisioning starves parallel
  # vitest suites on the host and flakes timing-sensitive tests. Counting live
  # containers makes MAX_EXTRA_RUNNERS a true concurrent ceiling and closes the
  # registration-lag double-count in one stroke.
  running_bursts="$(docker ps -q --filter 'name=gymboost-burst-' | wc -l)"
  room=$(( MAX_EXTRA_RUNNERS - running_bursts ))
  needed=$(( queued - idle ))
  (( needed > room )) && needed=$room

  if (( needed > 0 )); then
    log "queued=${queued} idle=${idle} live_bursts=${running_bursts} — starting ${needed} burst runner(s) (cap ${MAX_EXTRA_RUNNERS})"
    for _ in $(seq 1 "$needed"); do
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
