"""
Command execution and logging.
"""

import os
import subprocess
from datetime import datetime
from core.display import info, ok, warn

# The long-lived tool container started by docker/run.sh (repo root). Every
# real tool invocation (nmap/masscan/hydra/ncrack/ncat/evil-winrm) runs
# inside it via `docker exec`, never directly on this WSL2 host — the
# wizard's own orchestration (this process) still runs in WSL, only the
# tool subprocess itself is sandboxed. See docs/List การเเก้ไข.md item 5.
#
# No host-side sudo priming needed any more: nmap/masscan commands already
# come prefixed "sudo ..." (library/scanner.py), and the container's own
# sudoers rule (docker/Dockerfile) is NOPASSWD-scoped to exactly those two
# binaries, so `docker exec` reaches it non-interactively without this
# process ever touching a real password.
CONTAINER = os.environ.get("THERECON_CONTAINER", "therecon-tools")


def run_cmd(
    cmd: str,
    logfile: str | None = None,
    timeout: int = 600,
) -> tuple[str, int]:
    """
    Execute a shell command inside the TheRecon tool container and return
    (stdout+stderr, returncode). If logfile is provided, append the full
    output with a timestamp.
    """
    info(f"running: {cmd}")
    try:
        proc = subprocess.run(
            ["docker", "exec", "-i", CONTAINER, "bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        warn(f"command timed out after {timeout}s — killed")
        return "", 1
    except FileNotFoundError:
        warn("docker not found — is Docker Engine installed in this WSL distro?")
        return "", 1

    output = proc.stdout + proc.stderr

    if logfile:
        _append_log(logfile, cmd, output)

    if proc.returncode != 0:
        warn(f"exit code {proc.returncode}")
    else:
        ok("completed successfully")

    return output, proc.returncode


def _append_log(logfile: str, cmd: str, output: str) -> None:
    """Write a timestamped entry to the log file."""
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"# {datetime.now().isoformat()}\n")
        f.write(f"$ {cmd}\n")
        f.write(f"{output}\n\n")