"""
Ask the `llm` CLI to suggest a single nmap command line for a stated goal.

This never executes anything — it only returns text for the caller to show
the user, who can edit it before requesting execution. Whatever comes back
still has to pass `ConfirmationGate.request()` (validation + preview + exact
"yes") like any other command, same as CLAUDE.md's AI rule requires: no
AI-suggested command runs on the strength of the suggestion alone.

Kept separate from `src/core/llm_keys.py` (key management only) rather than
importing its private `_run()` helper, so this feature is a self-contained
addition.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional, Tuple

_TIMEOUT = 30
_LLM_BIN = '"$HOME/.local/bin/llm"'


def _run(argv: list) -> subprocess.CompletedProcess:
    if os.name == "nt":
        argv = ["wsl.exe", "-e"] + list(argv)
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=_TIMEOUT,
    )


# Same fixed function set the real `llm-tools-nmap` plugin (Kali packages /
# gitlab.com/kalilinux/packages/llm-tools-nmap) exposes to the model —
# nmap_scan/nmap_quick_scan/nmap_port_scan/nmap_service_detection/
# nmap_os_detection/nmap_ping_scan/nmap_script_scan. Constraining the prompt
# to this same short list (rather than letting the model invent arbitrary
# flags) keeps this panel's output matching what that plugin actually does —
# a handful of basic, well-understood scan types, not free-form flag
# construction.
_BASIC_FUNCTIONS = (
    "- quick scan: `-T4 -F` (fast common-port check)\n"
    "- port scan: `-p <ports>` (specific port(s)/range)\n"
    "- service detection: `-sV` (optionally with `-p <ports>`)\n"
    "- OS detection: `-O` (requires root)\n"
    "- ping/host-discovery scan: `-sn`\n"
    "- NSE script scan: `--script <script>` (optionally with `-p <ports>`)\n"
    "- generic scan: any other single, well-known nmap option combination\n"
)


def suggest_nmap_command(goal: str, target: str,
                          model: Optional[str] = None) -> Tuple[bool, str]:
    """Ask `llm` to map `goal` onto ONE of the basic scan types the real
    llm-tools-nmap plugin exposes (see `_BASIC_FUNCTIONS`), against
    `target`. Returns (True, "<command text>") on success, or
    (False, "<error message>") on failure (llm not installed, no key set,
    timeout, empty/garbage reply, ...)."""
    goal = (goal or "").strip()
    target = (target or "").strip()
    if not goal or not target:
        return False, "Goal and target are both required."

    prompt = (
        "You are choosing ONE basic nmap scan type for this request, the "
        f"same short list the llm-tools-nmap plugin supports:\n{_BASIC_FUNCTIONS}"
        f"Request: {goal}. Target: {target}. "
        "Reply with ONLY the resulting single nmap command line — no "
        "explanation, no markdown, no code fences, nothing before or "
        "after it. Do not invent flags outside this list."
    )
    model_args = ["-m", model] if model else []

    try:
        result = _run([
            "bash", "-lc",
            f'{_LLM_BIN} "$@"', "bash", *model_args, prompt,
        ])
    except subprocess.TimeoutExpired:
        return False, "Timed out waiting for the llm CLI to respond."
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "llm command failed").strip()

    reply = (result.stdout or "").strip()
    # Strip a stray ``` fence if the model added one anyway.
    if reply.startswith("```"):
        lines = [ln for ln in reply.splitlines() if not ln.strip().startswith("```")]
        reply = "\n".join(lines).strip()
    reply = reply.splitlines()[0].strip() if reply else ""

    if not reply:
        return False, "llm returned an empty reply."
    return True, reply
