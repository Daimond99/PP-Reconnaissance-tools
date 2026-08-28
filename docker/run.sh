#!/usr/bin/env bash
# Single, locked-down entry point for starting the TheRecon tool container.
# The app (executor.py / terminal_launch.py) calls THIS script, never
# `docker run` directly — so there is no code path anywhere that can
# accidentally add an unsafe flag (--privileged, docker.sock mount, etc).
# If a flag needs to change, it changes here, in one reviewable place.
set -euo pipefail

IMAGE="therecon-tools:latest"
CONTAINER="therecon-tools"
NETWORK="therecon-net"

# Host-side results directory — the only path shared with the container.
# Resolved relative to this script's location so it works from any clone.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/chain_wizard/results"
mkdir -p "$RESULTS_DIR"

# Optional wordlists directory — drop rockyou.txt etc here yourself; not
# baked into the image (see Dockerfile comment). Mounted read-only.
WORDLISTS_DIR="$SCRIPT_DIR/wordlists"
mkdir -p "$WORDLISTS_DIR"

docker network inspect "$NETWORK" >/dev/null 2>&1 \
    || docker network create "$NETWORK" >/dev/null

if docker inspect "$CONTAINER" >/dev/null 2>&1; then
    echo "[*] $CONTAINER already exists — removing before recreate" >&2
    docker rm -f "$CONTAINER" >/dev/null
fi

docker build -t "$IMAGE" "$SCRIPT_DIR"

# SETUID/SETGID: sudo (Dockerfile's scoped nmap/masscan-only sudoers rule)
# needs these to switch to root at all, even via its own setuid-root bit —
# cap-drop=ALL bounds what ANY process in this container can gain,
# setuid-root included, so without adding these back sudo itself fails
# with "unable to change to root gid" before it even reaches the sudoers
# check. Still nowhere near full root capabilities.
docker run -d \
    --name "$CONTAINER" \
    --network "$NETWORK" \
    --cap-drop=ALL \
    --cap-add=NET_RAW \
    --cap-add=NET_ADMIN \
    --cap-add=SETUID \
    --cap-add=SETGID \
    --read-only \
    --tmpfs /tmp:rw,size=256m \
    --tmpfs /run:rw,size=64m \
    --memory=1g \
    --cpus=2 \
    --pids-limit=256 \
    --restart unless-stopped \
    -v "$RESULTS_DIR:/results:rw" \
    -v "$WORDLISTS_DIR:/results/wordlists:ro" \
    "$IMAGE" >/dev/null

echo "[+] $CONTAINER running — exec in with:"
echo "    docker exec -it $CONTAINER bash"
