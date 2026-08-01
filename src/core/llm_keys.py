"""
Manage the `llm` CLI's stored API keys (`~/.config/io.datasette.llm/keys.json`,
inside WSL on Windows) for the LLM Mode page's llm-tools-nmap plugin.

Kept out of `src/ui/` per the architecture rule that the GUI never builds
commands or contains business logic — `main_window.py`'s Settings menu
handlers only call into this module.
"""

from __future__ import annotations

import os
import subprocess
from typing import Tuple

_TIMEOUT = 15

# Call the `llm` binary by its known pipx-install location instead of the
# bare `llm` name. WSL's interop launch doesn't reliably source ~/.profile
# before running a `bash -lc` command spawned from Python's subprocess.run
# (observed: works when spawned interactively, silently drops $HOME/.local/bin
# — where pipx installs `llm` — otherwise), and prepending an explicit
# `export PATH=...` is worse: the inherited PATH already leaking in from
# Windows interop contains entries like ".../Program Files (x86)/..." whose
# unescaped parentheses make bash's own command-line parser choke before the
# assignment is even reached. Calling the absolute path sidesteps PATH
# resolution entirely.
_LLM_BIN = '"$HOME/.local/bin/llm"'


def _run(argv: list) -> subprocess.CompletedProcess:
    if os.name == "nt":
        # `-e` executes the command directly instead of re-parsing it
        # through an extra default-shell layer first — without it,
        # $HOME-based paths built inside the -lc string can resolve wrong.
        argv = ["wsl.exe", "-e"] + list(argv)
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=_TIMEOUT,
    )


def has_llm_key(provider: str) -> bool:
    """True if `llm keys list` already shows an entry for `provider`."""
    try:
        result = _run(["bash", "-lc", f"{_LLM_BIN} keys list 2>/dev/null"])
    except Exception:
        return False
    names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return provider in names


def set_llm_key(provider: str, value: str) -> Tuple[bool, str]:
    """Save `value` under `provider` via `llm keys set <provider> --value
    <value>`. `provider`/`value` are passed as real argv elements (through
    bash's `$1`/`$2`), never interpolated into the shell command string, so
    arbitrary key content can't break out of the command."""
    try:
        result = _run([
            "bash", "-lc", f'{_LLM_BIN} keys set "$1" --value "$2"',
            "bash", provider, value,
        ])
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "llm keys set failed").strip()
    return True, f"Saved API key for '{provider}'."


def remove_llm_key(provider: str) -> Tuple[bool, str]:
    """Delete `provider`'s entry from keys.json. `llm keys` has no built-in
    remove subcommand (only list/get/path/set), so this edits the JSON file
    directly at the path `llm keys path` reports."""
    script = (
        "import json, os, sys\n"
        "p, k = sys.argv[1], sys.argv[2]\n"
        "d = json.load(open(p)) if os.path.exists(p) else {}\n"
        "existed = k in d\n"
        "d.pop(k, None)\n"
        "json.dump(d, open(p, 'w'), indent=2)\n"
        "sys.exit(0 if existed else 1)\n"
    )
    try:
        result = _run([
            "bash", "-lc",
            f'p=$({_LLM_BIN} keys path) && python3 -c "$1" "$p" "$2"',
            "bash", script, provider,
        ])
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if result.returncode != 0:
        return False, f"No stored key found for '{provider}'."
    return True, f"Removed API key for '{provider}'."
