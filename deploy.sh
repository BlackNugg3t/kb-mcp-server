#!/usr/bin/env bash
# One-time bootstrap for a fresh Debian box: installs Docker if missing,
# validates .env, builds the KB + runner images, and (if `gh` is available
# and authenticated) syncs CLAUDE_CODE_OAUTH_TOKEN to the target repo's
# GitHub Actions secrets. Does NOT start containers — run ./run.sh for that.
#
# Usage:
#   git clone git@github.com:BlackNugg3t/kb-mcp-server.git
#   cd kb-mcp-server
#   ./deploy.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

REQUIRED_VARS=(KB_AUTH_TOKEN GH_RUNNER_PAT GH_RUNNER_REPO_URL CLAUDE_CODE_OAUTH_TOKEN)

log()  { printf '\033[1;34m[deploy]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$1" >&2; }
die()  { printf '\033[1;31m[deploy]\033[0m %s\n' "$1" >&2; exit 1; }

# ── 1. .env bootstrap ──────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  die "Created .env from .env.example — fill in the tokens listed there, then rerun ./deploy.sh."
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

missing=()
for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("$var")
  fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
  die "Missing required .env values: ${missing[*]} — fill these in before deploying."
fi

# ── 2. Docker Engine + Compose plugin (Debian) ─────────────────────────────
if ! command -v docker &>/dev/null; then
  log "Docker not found — installing Docker Engine (official apt repo)..."
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  DEBIAN_CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${DEBIAN_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker already installed, skipping install."
fi

if ! groups "$USER" | grep -q '\bdocker\b'; then
  log "Adding $USER to the docker group (log out/in — or run 'newgrp docker' — for this to take effect)."
  sudo usermod -aG docker "$USER"
fi

DOCKER="docker"
if ! docker info &>/dev/null; then
  # Group membership not active in this shell yet — fall back to sudo for
  # the rest of this run so deploy.sh works in one shot.
  DOCKER="sudo docker"
fi

# ── 3. Build images ─────────────────────────────────────────────────────────
log "Building KB + runner images..."
$DOCKER compose -f docker-compose.yml -f docker-compose.runner.yml build

# ── 4. Sync secrets to GitHub (optional, best-effort) ──────────────────────
REPO="$(echo "$GH_RUNNER_REPO_URL" | sed -E 's#https://github.com/##; s#\.git$##')"

if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  # `.env` is the source of truth for CLAUDE_CODE_OAUTH_TOKEN — rotate the
  # token there and `./deploy.sh` pushes it to the repo. That is deliberate:
  # one place to edit, not two.
  #
  # What bit us on 2026-08-06 was not the sync itself but that it was SILENT.
  # A deploy run to ship an unrelated runner fix pushed a stale .env value over
  # a working secret, and every agent job afterwards died in ~350-800ms with
  # is_error:true and total_cost_usd:0 — a rejected token — while the runner,
  # the labels and the workflows all looked perfectly healthy. Nothing in the
  # deploy output hinted that a live credential had just been replaced.
  #
  # So: still sync from .env, but refuse obvious junk and say loudly when an
  # existing secret is being overwritten.
  if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN// /}" ]]; then
    die "CLAUDE_CODE_OAUTH_TOKEN is empty in .env — refusing to overwrite the repo secret with nothing."
  fi
  case "$CLAUDE_CODE_OAUTH_TOKEN" in
    *your-token-here* | *changeme* | *placeholder* | *xxxxx* | *REPLACE_ME*)
      die "CLAUDE_CODE_OAUTH_TOKEN in .env still looks like a placeholder — refusing to push it over the live secret." ;;
  esac
  if [[ "$CLAUDE_CODE_OAUTH_TOKEN" != sk-ant-* ]]; then
    warn "CLAUDE_CODE_OAUTH_TOKEN does not start with 'sk-ant-' — double-check it is a real Claude Code OAuth token."
  fi

  if gh secret list --repo "$REPO" --json name --jq '.[].name' 2>/dev/null \
       | grep -qx CLAUDE_CODE_OAUTH_TOKEN; then
    warn "OVERWRITING the existing CLAUDE_CODE_OAUTH_TOKEN on ${REPO} with this host's .env value."
    warn "  If agent jobs start failing in under a second at \$0 cost, this line is why — the .env token is stale."
  else
    log "CLAUDE_CODE_OAUTH_TOKEN not set on ${REPO} yet — syncing from .env."
  fi
  gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo "$REPO" --body "$CLAUDE_CODE_OAUTH_TOKEN"
  log "CLAUDE_CODE_OAUTH_TOKEN synced. Verify: gh secret list --repo ${REPO}"

  # PAT_TOKEN keeps its original set-once behaviour — it is the runner's own
  # registration credential and is not rotated as part of a routine deploy.
  if ! gh secret list --repo "$REPO" --json name --jq '.[].name' 2>/dev/null \
       | grep -qx PAT_TOKEN; then
    log "PAT_TOKEN not set on ${REPO} yet — syncing GH_RUNNER_PAT as PAT_TOKEN."
    gh secret set PAT_TOKEN --repo "$REPO" --body "$GH_RUNNER_PAT"
  fi
else
  warn "gh CLI not found or not authenticated — skipping secret sync."
  warn "Set CLAUDE_CODE_OAUTH_TOKEN manually: gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo ${REPO}"
fi

# ── 5. Restart any systemd units running this code ─────────────────────────
#
# The RUNNER has no systemd unit by design — `restart: unless-stopped` plus
# Docker's own service handle it (see run.sh). But the KB units in systemd/
# run `python3 -m src.main serve` directly from this working directory, so a
# deploy that changes the code leaves a running unit executing the OLD code
# until something restarts it. Neither this script nor run.sh used to do that.
#
# Only touches units that are actually installed AND active — this is a no-op
# on a host that runs the KB via ./run-kb.sh (docker compose) or not at all.
if command -v systemctl &>/dev/null; then
  for unit in kb-mcp-server.service kb-scanner.timer; do
    if systemctl is-active --quiet "$unit" 2>/dev/null; then
      log "Restarting active systemd unit ${unit} so it picks up the new code..."
      sudo systemctl restart "$unit" || warn "Failed to restart ${unit} — restart it by hand."
    elif systemctl list-unit-files 2>/dev/null | grep -q "^${unit}"; then
      log "${unit} is installed but not active — leaving it stopped."
    fi
  done
else
  warn "systemctl not found — skipping systemd restart step."
fi

log "Deploy complete. Run ./run.sh to start the runner (./run-kb.sh for the KB)."
log "Then check everything with ./status.sh"
