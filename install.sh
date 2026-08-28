#!/usr/bin/env bash
# TheRecon — one-command installer (Linux native, Debian/Ubuntu/Kali apt-based).
# Installs Docker Engine, builds + starts the sandboxed tool container
# (docker/run.sh — the 6 authorized tools run only inside it, never on this
# host directly, see docs/List การเเก้ไข.md item 5) + Python venv + deps.
# Idempotent — safe to re-run.
#
# Two ways to run it:
#   1. Already have a checkout: `cd TheRecon && ./install.sh`
#   2. One-liner, no checkout yet:
#      curl -fsSL https://raw.githubusercontent.com/Daimond99/TheRecon/main/install.sh | bash
#      (clones into $THERECON_DIR, default ~/TheRecon)
set -euo pipefail

REPO_URL="https://github.com/Daimond99/TheRecon.git"

log()  { printf '\n[install.sh] %s\n' "$1"; }
fail() { printf '\n[install.sh] ERROR: %s\n' "$1" >&2; exit 1; }

if [ "$(id -u)" -eq 0 ]; then
    fail "don't run as root — script uses sudo where needed"
fi

command -v apt-get >/dev/null 2>&1 || fail "apt-get not found — this script targets Debian/Ubuntu/Kali only"
command -v git >/dev/null 2>&1 || fail "git not found — install it first (sudo apt-get install -y git)"
command -v python3 >/dev/null 2>&1 || fail "python3 not found — install it first"

# Running from inside an existing checkout (./install.sh) vs. piped via curl
# (no local checkout yet, BASH_SOURCE doesn't resolve to a real file) --
# detect by checking for our own repo markers next to this script.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-/nonexistent}")" >/dev/null 2>&1 && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/CLAUDE.md" ] && [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    REPO_DIR="$SCRIPT_DIR"
    log "running from existing checkout: $REPO_DIR"
else
    REPO_DIR="${THERECON_DIR:-$HOME/TheRecon}"
    # On WSL, cloning onto the Windows filesystem (/mnt/c/...) can fail
    # with "chmod on .git/config.lock failed: Operation not permitted" --
    # DrvFs doesn't fully support the permissions git needs. $HOME/TheRecon
    # (the default) is already a native Linux path, so this only fires if
    # $THERECON_DIR was explicitly pointed at /mnt/...
    case "$REPO_DIR" in
        /mnt/*)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                log "WARNING: \$THERECON_DIR ($REPO_DIR) is on the Windows filesystem (/mnt/...) -- 'git clone' there often fails on WSL (DrvFs permissions). Prefer a native Linux path, e.g. \$HOME/TheRecon."
            fi
            ;;
    esac
    if [ -d "$REPO_DIR/.git" ]; then
        log "repo already at $REPO_DIR, pulling latest"
        git -C "$REPO_DIR" pull --ff-only
    else
        log "cloning into $REPO_DIR"
        git clone "$REPO_URL" "$REPO_DIR"
    fi
fi

log "installing Docker Engine via apt"
sudo apt-get update
sudo apt-get install -y docker.io python3-pip python3-venv
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

cd "$REPO_DIR"

log "building + starting the sandboxed tool container (docker/run.sh)"
chmod +x docker/run.sh
# `sg docker` picks up the group just added above for this one command,
# without needing a fresh login/shell (which `usermod` alone would need) --
# running the whole script as root instead would make it own the results/
# mount, which the container's own non-root user then can't write into.
sg docker -c "./docker/run.sh"

log "creating Python venv (.venv)"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    log ".venv already exists, reusing"
fi

log "installing Python deps"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Final gate: the dependency doctor re-checks the 6 tools + python from the
# app's own point of view and prints an exact fix for anything still
# missing. Non-fatal (|| true) so a partial install still reaches the run
# instructions below.
log "running preflight doctor"
.venv/bin/python -m src.preflight || true

log "done. run the app with:"
printf "\n  cd '%s'\n  source .venv/bin/activate\n  python -m src.main\n\n" "$REPO_DIR"
