#!/usr/bin/env bash
# One-shot health report for the self-hosted runner pool.
#
# Answers, in order: are the containers up, does GitHub agree with what's
# actually running, is anything leaking or starving, and what do the logs say.
# Read-only — it never starts, stops or deletes anything.
#
# Usage:
#   ./status.sh              # full report
#   ./status.sh --logs 40    # more log lines per container (default 12)
#   ./status.sh --no-color
set -uo pipefail   # NOT -e: this script must survive every probe failing.

cd "$(dirname "${BASH_SOURCE[0]}")"

LOG_LINES=12
USE_COLOR=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --logs) LOG_LINES="${2:-12}"; shift 2 ;;
    --no-color) USE_COLOR=0; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ $USE_COLOR == 1 && -t 1 ]]; then
  R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; B=$'\e[34m'; DIM=$'\e[2m'; BOLD=$'\e[1m'; N=$'\e[0m'
else
  R=""; G=""; Y=""; B=""; DIM=""; BOLD=""; N=""
fi

OK="${G}●${N}"; WARN="${Y}●${N}"; BAD="${R}●${N}"

# Findings accumulate here and are replayed as the verdict at the end.
PROBLEMS=(); NOTES=()
problem() { PROBLEMS+=("$1"); }
note()    { NOTES+=("$1"); }

hr()      { printf '%s\n' "${DIM}────────────────────────────────────────────────────────────────${N}"; }
section() { printf '\n%s\n' "${BOLD}${B}$1${N}"; hr; }

DOCKER="docker"
docker info &>/dev/null || DOCKER="sudo docker"

# ── GitHub API access ───────────────────────────────────────────────────────
# Prefer the host's gh; fall back to the copy inside runner-watcher so this
# works on a box that never installed gh. Both use the PAT from .env.
[[ -f .env ]] && set -a && . ./.env 2>/dev/null && set +a
REPO=""
[[ -n "${GH_RUNNER_REPO_URL:-}" ]] && \
  REPO="$(echo "$GH_RUNNER_REPO_URL" | sed -E 's#https://github.com/##; s#\.git$##')"

GH_MODE="none"
if command -v gh &>/dev/null && [[ -n "${GH_RUNNER_PAT:-}" ]]; then
  GH_MODE="host"                       # host gh, PAT from .env
elif $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -qx runner-watcher; then
  GH_MODE="container"                  # borrow the watcher's gh + its token
elif command -v gh &>/dev/null && gh auth status &>/dev/null; then
  GH_MODE="hostauth"                   # host gh already logged in as a human
fi

gh_api() { # $1 = path, $2 = --jq expression
  case "$GH_MODE" in
    host)      GH_TOKEN="$GH_RUNNER_PAT" gh api "$1" --jq "$2" 2>&1 ;;
    hostauth)  gh api "$1" --jq "$2" 2>&1 ;;
    container) $DOCKER exec -e GH_TOKEN="${GH_RUNNER_PAT:-}" runner-watcher \
                 gh api "$1" --jq "$2" 2>&1 ;;
    *)         echo "__NOAPI__" ;;
  esac
}

printf '%s\n' "${BOLD}gymboost runner status — $(date '+%Y-%m-%d %H:%M:%S %Z')${N}"
printf '%s\n' "${DIM}host $(hostname)   repo ${REPO:-<unknown>}   cap ${GH_RUNNER_MAX_EXTRA:-unset}${N}"

# ── 1. Core containers ──────────────────────────────────────────────────────
section "Core containers"
printf '%-18s %-9s %-22s %-8s %s\n' "NAME" "STATE" "UPTIME" "RESTARTS" "IMAGE"
for c in gh-runner runner-watcher; do
  if ! $DOCKER inspect "$c" &>/dev/null; then
    printf '%s %-16s %-9s %-22s %-8s %s\n' "$BAD" "$c" "absent" "—" "—" "${R}never created${N}"
    problem "$c container does not exist — run ./run.sh"
    continue
  fi
  state=$($DOCKER inspect -f '{{.State.Status}}' "$c" 2>/dev/null)
  since=$($DOCKER inspect -f '{{.State.StartedAt}}' "$c" 2>/dev/null)
  restarts=$($DOCKER inspect -f '{{.RestartCount}}' "$c" 2>/dev/null)
  image=$($DOCKER inspect -f '{{.Config.Image}}' "$c" 2>/dev/null)
  human=$($DOCKER ps -a --filter "name=^${c}$" --format '{{.Status}}' 2>/dev/null)

  mark=$OK
  [[ "$state" != "running" ]] && { mark=$BAD; problem "$c is '$state', not running"; }
  if [[ "${restarts:-0}" -gt 5 ]]; then
    mark=$WARN
    problem "$c has restarted ${restarts}× — it is crash-looping, read its log below"
  fi
  printf '%s %-16s %-9s %-22s %-8s %s\n' "$mark" "$c" "$state" "${human:0:22}" "${restarts:-?}" "$image"
done

# The bug that cost us a day: EPHEMERAL is a presence flag in the base image,
# so EPHEMERAL=false turns ephemeral mode ON and the persistent runner starts
# recycling itself after every job.
if $DOCKER inspect gh-runner &>/dev/null; then
  if $DOCKER inspect -f '{{range .Config.Env}}{{println .}}{{end}}' gh-runner 2>/dev/null \
      | grep -q '^EPHEMERAL='; then
    val=$($DOCKER inspect -f '{{range .Config.Env}}{{println .}}{{end}}' gh-runner \
          | grep '^EPHEMERAL=' | head -1)
    printf '\n%s %s\n' "$BAD" "${R}gh-runner has ${val} set.${N}"
    printf '   %s\n' "${DIM}The base image treats EPHEMERAL as a presence flag — ANY value, including${N}"
    printf '   %s\n' "${DIM}\"false\", enables ephemeral mode. The persistent runner will take one job,${N}"
    printf '   %s\n' "${DIM}deregister and restart-loop. Remove the line from docker-compose.runner.yml${N}"
    printf '   %s\n' "${DIM}entirely, then: ./run.sh${N}"
    problem "gh-runner has EPHEMERAL set — it is not actually a persistent runner"
  fi
fi

# ── 2. Burst runners ────────────────────────────────────────────────────────
section "Burst runners (live containers)"
mapfile -t BURSTS < <($DOCKER ps --filter 'name=gymboost-burst-' \
                        --format '{{.Names}}\t{{.Status}}' 2>/dev/null)
CAP="${GH_RUNNER_MAX_EXTRA:-4}"
if [[ ${#BURSTS[@]} -eq 0 ]]; then
  printf '%s none live %s\n' "$OK" "${DIM}(scale-to-zero — normal when the queue is empty)${N}"
else
  for b in "${BURSTS[@]}"; do printf '%s %s\n' "$OK" "$b"; done
fi
printf '\n%s\n' "live=${#BURSTS[@]}  cap=${CAP}"
if [[ ${#BURSTS[@]} -gt $CAP ]]; then
  printf '%s %s\n' "$BAD" "${R}OVER CAP — watch-queue.sh is over-provisioning${N}"
  problem "burst runners (${#BURSTS[@]}) exceed cap (${CAP})"
fi
# Each burst runner competes for the same RAM/CPU as everything else on this
# box, and nothing in watch-queue.sh sets --memory/--cpus on them.
if [[ ${#BURSTS[@]} -ge $CAP ]]; then
  note "burst pool is at its cap (${CAP}) — no room to scale further. If jobs are queuing, either the cap is too low for the workload or some of these containers are zombies (see the cross-reference below)."
fi

# ── 3. GitHub's view, cross-referenced ──────────────────────────────────────
section "GitHub registrations vs. reality"
if [[ "$GH_MODE" == "none" || -z "$REPO" ]]; then
  printf '%s %s\n' "$WARN" "skipped — no gh CLI on host and runner-watcher is down (or .env unreadable)"
  note "could not query GitHub; install gh or start runner-watcher for the full picture"
else
  runners=$(gh_api "repos/${REPO}/actions/runners" \
    '.runners[] | "\(.name)\t\(.status)\t\(.busy)"')
  if [[ "$runners" == *"HTTP 50"* || "$runners" == *"service unavailable"* || "$runners" == *"Server Error"* ]]; then
    printf '%s %s\n' "$WARN" "${Y}GitHub API is erroring:${N} ${runners:0:100}"
    note "GitHub's runner API is returning 5xx — registrations below are unknown, NOT empty. Wait it out; watch-queue.sh skips cycles while this lasts."
  elif [[ -z "$runners" || "$runners" == "__NOAPI__" ]]; then
    printf '%s %s\n' "$BAD" "${R}no runners registered at all${N}"
    problem "GitHub lists zero registered runners — jobs will queue forever"
  else
    # Guard: if this box runs NO runner containers at all but GitHub lists
    # registrations, we are almost certainly not on the runner host. Without
    # this, every row below reads "leaked" and the report is pure noise.
    OFF_HOST=0
    if ! $DOCKER ps --format '{{.Names}}' 2>/dev/null \
         | grep -qE '^(gh-runner|gymboost-burst-)'; then
      OFF_HOST=1
      printf '%s %s\n\n' "$WARN" \
        "${Y}No runner containers on this host — the CONTAINER column below is not meaningful.${N}"
      note "this does not look like the runner host (no gh-runner, no burst containers). Run ./status.sh on the runner box for the container cross-reference."
    fi
    printf '%-34s %-9s %-6s %s\n' "NAME" "STATUS" "BUSY" "CONTAINER"
    while IFS=$'\t' read -r name status busy; do
      [[ -z "$name" ]] && continue
      if [[ $OFF_HOST -eq 1 ]]; then
        here="${DIM}n/a${N}"
      elif $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -qx "$name"; then
        here="${G}live${N}"
      elif [[ "$name" == "${GH_RUNNER_NAME:-gymboost-runner-01}" ]]; then
        here=$($DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -qx gh-runner \
               && echo "${G}gh-runner${N}" || echo "${R}absent${N}")
      else
        here="${R}absent — leaked${N}"
      fi
      mark=$OK
      [[ "$status" != "online" ]] && mark=$WARN
      [[ "$status" != "online" && "$busy" == "true" ]] && {
        mark=$BAD
        problem "$name is offline while holding a job (busy=true) — it was killed mid-job; that job gets cancelled"
      }
      [[ "$here" == *"leaked"* ]] && \
        note "$name is registered on GitHub but has no container — stale registration, delete with: gh api -X DELETE repos/${REPO}/actions/runners/<id>"
      printf '%s %-32s %-9s %-6s %b\n' "$mark" "$name" "$status" "$busy" "$here"
    done <<< "$runners"

    # ── Zombie burst runners ────────────────────────────────────────────────
    # The inverse of a leaked registration, and the one that actually hurts.
    # A burst runner is meant to live for exactly one job: register, run it,
    # deregister, exit, `--rm` removes the container. A container that is
    # alive but NOT online to GitHub (offline, or never registered at all)
    # will never be handed work again — yet watch-queue.sh still counts it
    # via `docker ps`, so it permanently consumes a slot of MAX_EXTRA_RUNNERS.
    # Enough of these and the pool cannot scale even though it looks busy.
    if [[ $OFF_HOST -eq 0 && ${#BURSTS[@]} -gt 0 ]]; then
      # Names GitHub currently considers online, one per line.
      online_names=$(awk -F'\t' '$2 == "online" { print $1 }' <<< "$runners")
      zombies=0
      for entry in "${BURSTS[@]}"; do
        bname="${entry%%$'\t'*}"
        if ! grep -qxF "$bname" <<< "$online_names"; then
          zombies=$((zombies + 1))
          printf '%s %s\n' "$BAD" \
            "${R}zombie:${N} ${bname} — container alive but not online to GitHub"
        fi
      done
      if [[ $zombies -gt 0 ]]; then
        problem "${zombies} burst container(s) are alive but not online to GitHub — they cannot take jobs, yet they occupy ${zombies}/${CAP} of the burst budget (room left: $((CAP - ${#BURSTS[@]}))). Clear them: docker rm -f \$(docker ps -q --filter name=gymboost-burst-)"
      fi
    fi
  fi

  queued=$(gh_api "repos/${REPO}/actions/runs?status=queued" '.total_count')
  inprog=$(gh_api "repos/${REPO}/actions/runs?status=in_progress" '.total_count')
  printf '\nqueued=%s  in_progress=%s\n' "${queued:-?}" "${inprog:-?}"
  if [[ "${queued:-0}" =~ ^[0-9]+$ && "${queued:-0}" -gt 0 ]]; then
    idle_now=$(gh_api "repos/${REPO}/actions/runners" \
      '[.runners[] | select(.status == "online" and .busy == false)] | length')
    [[ "${idle_now:-0}" =~ ^[0-9]+$ && "${idle_now:-0}" -eq 0 && ${#BURSTS[@]} -eq 0 ]] && \
      problem "${queued} job(s) queued with no idle runner and no burst runners starting — the pool is not serving the queue"
  fi
fi

# ── 4. Resource usage ───────────────────────────────────────────────────────
section "Resources"
printf '%s\n' "${DIM}host${N}"
uptime | sed 's/^/  /'
free -h 2>/dev/null | sed 's/^/  /'
df -h / 2>/dev/null | tail -n +1 | sed 's/^/  /'

avail_mb=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
if [[ -n "$avail_mb" && "$avail_mb" -lt 1024 ]]; then
  printf '\n%s %s\n' "$BAD" "${R}only ${avail_mb}MB RAM available${N}"
  problem "host is low on memory (${avail_mb}MB available) — this is what OOM-kills runners mid-job"
fi

printf '\n%s\n' "${DIM}runner containers${N}"
names=$($DOCKER ps --format '{{.Names}}' 2>/dev/null \
        | grep -E '^(gh-runner|runner-watcher|gymboost-burst-)' | tr '\n' ' ')
if [[ -n "${names// /}" ]]; then
  # shellcheck disable=SC2086
  $DOCKER stats --no-stream --format \
    'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}' $names 2>/dev/null | sed 's/^/  /'
else
  printf '  %s\n' "${DIM}no runner containers running${N}"
fi

# ── 5. systemd (KB only — the runner deliberately has no unit) ──────────────
section "systemd units"
if command -v systemctl &>/dev/null; then
  found=0
  for unit in kb-mcp-server.service kb-scanner.service kb-scanner.timer; do
    if systemctl list-unit-files 2>/dev/null | grep -q "^${unit}"; then
      found=1
      st=$(systemctl is-active "$unit" 2>/dev/null)
      mark=$OK; [[ "$st" != "active" ]] && mark=$WARN
      printf '%s %-26s %s\n' "$mark" "$unit" "$st"
      # Both paths serve :9020; running them together is a port fight.
      if [[ "$unit" == "kb-mcp-server.service" && "$st" == "active" ]] \
         && $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -qx mcp-server; then
        problem "kb-mcp-server.service AND the mcp-server container are both running — they both bind :9020, pick one"
      fi
    fi
  done
  [[ $found -eq 0 ]] && printf '%s\n' "${DIM}none installed (expected — the runner uses Docker restart policies, not systemd)${N}"
else
  printf '%s\n' "${DIM}systemctl not available${N}"
fi

# ── 6. Logs ─────────────────────────────────────────────────────────────────
section "Recent logs (last ${LOG_LINES} lines)"
any_logs=0
for c in gh-runner runner-watcher; do
  $DOCKER inspect "$c" &>/dev/null || continue
  any_logs=1
  printf '\n%s\n' "${BOLD}${c}${N}"
  $DOCKER logs --tail "$LOG_LINES" "$c" 2>&1 | sed 's/^/  /'
done
[[ $any_logs -eq 0 ]] && printf '%s\n' "${DIM}no containers to read logs from${N}"

if $DOCKER inspect gh-runner &>/dev/null; then
  if $DOCKER logs --tail 200 gh-runner 2>&1 | grep -q "was not found"; then
    problem "gh-runner log shows 'Registration ... was not found' — it is re-registering in a loop (see the EPHEMERAL check above)"
  fi
  $DOCKER logs --tail 50 gh-runner 2>&1 | grep -q "Listening for Jobs" \
    || note "gh-runner has not printed 'Listening for Jobs' recently — it may still be registering, or failing to"
fi

# ── 7. Verdict ──────────────────────────────────────────────────────────────
printf '\n'; hr
if [[ ${#PROBLEMS[@]} -eq 0 ]]; then
  printf '%s %s\n' "$OK" "${G}${BOLD}HEALTHY${N} — containers up, every live runner is online to GitHub, nothing stuck."
else
  printf '%s %s\n' "$BAD" "${R}${BOLD}${#PROBLEMS[@]} PROBLEM(S)${N}"
  for p in "${PROBLEMS[@]}"; do printf '   %s %s\n' "${R}✗${N}" "$p"; done
fi
if [[ ${#NOTES[@]} -gt 0 ]]; then
  printf '\n%s\n' "${Y}notes${N}"
  for n in "${NOTES[@]}"; do printf '   %s %s\n' "${Y}!${N}" "$n"; done
fi
printf '\n'
[[ ${#PROBLEMS[@]} -eq 0 ]]
