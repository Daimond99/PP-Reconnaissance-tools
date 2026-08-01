#!/usr/bin/env bash
# TheRecon — one-command installer (Linux native, Debian/Ubuntu/Kali apt-based).
# Installs the 6 authorized tools + Python venv + deps. Idempotent — safe to
# re-run. Does NOT run the app or touch anything outside this repo / apt / gem.
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
    if [ -d "$REPO_DIR/.git" ]; then
        log "repo already at $REPO_DIR, pulling latest"
        git -C "$REPO_DIR" pull --ff-only
    else
        log "cloning into $REPO_DIR"
        git clone "$REPO_URL" "$REPO_DIR"
    fi
fi

log "installing the 6 authorized tools (nmap masscan hydra ncrack ncat ruby) via apt"
sudo apt-get update
sudo apt-get install -y nmap masscan hydra ncrack ncat ruby ruby-dev \
    python3-pip python3-venv

log "installing evil-winrm via gem"
sudo gem install evil-winrm

log "verifying tool versions"
for t in nmap masscan hydra ncrack ncat; do
    if command -v "$t" >/dev/null 2>&1; then
        printf '  %-10s %s\n' "$t" "$("$t" --version 2>&1 | head -n1)"
    else
        printf '  %-10s NOT FOUND\n' "$t"
    fi
done
if command -v evil-winrm >/dev/null 2>&1; then
    printf '  %-10s %s\n' "evil-winrm" "$(evil-winrm --version 2>&1 | head -n1)"
else
    printf '  %-10s NOT FOUND (check gem install output above)\n' "evil-winrm"
fi

cd "$REPO_DIR"

log "creating Python venv (.venv)"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    log ".venv already exists, reusing"
fi

log "installing Python deps"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

log "done. run the app with:"
printf "\n  cd '%s'\n  source .venv/bin/activate\n  python -m src.main\n\n" "$REPO_DIR"
