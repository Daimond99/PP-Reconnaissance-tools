"""
Command execution and logging.
"""

import subprocess
from datetime import datetime
from core.display import info, ok, warn


def run_cmd(
    cmd: str,
    logfile: str | None = None,
    timeout: int = 600,
) -> tuple[str, int]:
    """
    Execute a shell command and return (stdout+stderr, returncode).
    If logfile is provided, append the full output with a timestamp.
    """
    info(f"running: {cmd}")
    if cmd.lstrip().startswith("sudo "):
        # Prime/refresh sudo's own tty-timestamp cache before the real
        # command runs, on the same controlling tty this PTY session
        # already has. First sudo-prefixed command in a run prompts once
        # (same /dev/tty mechanism as the command itself would use);
        # every later one within the cache window succeeds silently and
        # extends it, so masscan/nmap steps stop re-prompting on every
        # single invocation.
        try:
            subprocess.run(["sudo", "-v"], timeout=120)
        except subprocess.TimeoutExpired:
            warn("sudo password prompt timed out")
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        warn(f"command timed out after {timeout}s — killed")
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