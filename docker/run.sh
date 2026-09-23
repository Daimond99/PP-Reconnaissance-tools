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
# Host UID (this script's caller) rarely matches the container's `recon`
# UID, and root inside the container can't fall back on DAC override to
# write anyway (--cap-drop=ALL below strips CAP_DAC_OVERRIDE on purpose).
# world-writable is fine here -- /results only ever holds scan output /
# the OpenCode workspace, nothing sensitive, and it's already the one
# read-write mount shared with the sandboxed container by design.
chmod 777 "$RESULTS_DIR"

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
#
# CHOWN: the OpenCode workspace setup pass (terminal_launch.py) runs
# `chown -R recon:recon` on /results/opencode-{workspace,home} as root, to
# hand those dirs to the `recon` user OpenCode itself runs as (their UIDs
# rarely match the host UID that owns the /results bind mount). Root's
# own uid=0 isn't enough for that once cap-drop=ALL strips CAP_CHOWN too.
#
# /opt/oc-tmp: a second, `exec`-enabled tmpfs used ONLY as OpenCode's
# `$TMPDIR` (src/ui/terminal_launch.py::_opencode_launch) -- its OpenTUI
# render library extracts and `dlopen()`s a native `.so` into whatever
# `$TMPDIR` resolves to at startup, which fails outright
# ("failed to map segment from shared object") on the main `/tmp` above,
# mounted `noexec` on purpose. Kept separate from `/tmp` instead of just
# dropping `noexec` there, so nothing else in the container (nmap,
# masscan, ...) gains the ability to execute a file written to `/tmp`.
docker run -d \
    --name "$CONTAINER" \
    --network "$NETWORK" \
    --cap-drop=ALL \
    --cap-add=NET_RAW \
    --cap-add=NET_ADMIN \
    --cap-add=SETUID \
    --cap-add=SETGID \
    --cap-add=CHOWN \
    --read-only \
    --tmpfs /tmp:rw,size=256m \
    --tmpfs /run:rw,size=64m \
    --tmpfs /opt/oc-tmp:rw,exec,nosuid,nodev,mode=1777,size=64m \
    --memory=1g \
    --cpus=2 \
    --pids-limit=256 \
    --restart unless-stopped \
    -v "$RESULTS_DIR:/results:rw" \
    -v "$WORDLISTS_DIR:/results/wordlists:ro" \
    "$IMAGE" >/dev/null

echo "[+] $CONTAINER running — exec in with:"
echo "    docker exec -it $CONTAINER bash"
