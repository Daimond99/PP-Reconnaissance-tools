"""
Generic, tool-agnostic input validation.

Validators only validate — they never build or execute commands
(docs/Resource System.md #10, "Validators never generate commands").
"""

from __future__ import annotations

import re
import shlex
from typing import List, Tuple

_DANGEROUS_SHELL_CHARS = set(";|&`$()<>\\")


def _has_unquoted_shell_metachar(command: str) -> str | None:
    """Scan `command` char by char, honoring `"..."` / `'...'` regions —
    return the first dangerous metacharacter that appears OUTSIDE any
    quoted region, or None if all uses are safely quoted. Lets things
    like hydra's `http-post-form "/login:user=^USER^&pass=^PASS^:F=X"`
    pass (the `&` is inside `"..."` — bash treats it literally there)
    while still rejecting a bare `foo; rm -rf /` or `foo | bar`."""
    i, in_single, in_double, escape = 0, False, False, False
    while i < len(command):
        c = command[i]
        if escape:
            escape = False
        elif in_single:
            if c == "'":
                in_single = False
        elif in_double:
            if c == "\\":
                escape = True
            elif c == '"':
                in_double = False
        else:
            if c == "'":
                in_single = True
            elif c == '"':
                in_double = True
            elif c in _DANGEROUS_SHELL_CHARS:
                return c
        i += 1
    return None

# Programs any generated/AI-suggested command line is allowed to invoke.
ALLOWED_PROGRAMS = {
    "nmap", "masscan", "hydra", "ncrack", "ncat",
    "evil-winrm", "gobuster", "dirb",
}

# Matches a Windows drive-letter path (e.g. a wordlist typed/pasted from
# Explorer) in quoted or bare form, so it can be rewritten to the WSL
# mount-point equivalent before DANGEROUS_SHELL_CHARS (which blocks bare
# backslash) ever sees it.
_WIN_DRIVE_PATH_RE = re.compile(
    r'"([A-Za-z]):\\([^"]*)"'
    r"|'([A-Za-z]):\\([^']*)'"
    r"|([A-Za-z]):\\(\S*)"
)


def convert_windows_paths_to_wsl(command: str) -> str:
    """Rewrite any `C:\\...`-style path in `command` to its WSL mount-point
    form (`/mnt/c/...`) — the actual execution shell on Windows is WSL bash
    (src/ui/terminal_tabs.py), which has no notion of a Windows drive
    letter. Only touches substrings that actually look like a drive-letter
    path; everything else in the command is left untouched."""

    def _repl(m: "re.Match[str]") -> str:
        if m.group(1) is not None:
            drive, rest, quote = m.group(1), m.group(2), '"'
        elif m.group(3) is not None:
            drive, rest, quote = m.group(3), m.group(4), "'"
        else:
            drive, rest, quote = m.group(5), m.group(6), ""
        wsl_path = f"/mnt/{drive.lower()}/{rest.replace(chr(92), '/')}"
        return f"{quote}{wsl_path}{quote}"

    return _WIN_DRIVE_PATH_RE.sub(_repl, command)


def validate_exact_confirmation(value: str) -> bool:
    """Only the literal string 'yes' (case-sensitive) counts as confirmation.
    Anything else — including 'y', 'Yes', empty Enter, or 'no' — cancels."""
    return value == "yes"


def parse_command_line(command: str) -> Tuple[bool, str, List[str]]:
    """
    Parse a full command string into [program, arg1, arg2, ...] and check
    the program against the allow-list. Returns (ok, error_message, argv).
    """
    command = command.strip()
    if not command:
        return False, "Empty command.", []

    bad_char = _has_unquoted_shell_metachar(command)
    if bad_char:
        return False, f"Command contains disallowed unquoted shell metacharacter: {bad_char!r}", []

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return False, f"Could not parse command: {exc}", []

    if not tokens:
        return False, "Empty command.", []

    # Allow a bare `sudo` prefix — masscan/nmap raw-socket flags (-sS, -O)
    # fail with "permission denied" unrooted in WSL, and `setcap` isn't
    # always set up. Only the bare form (no sudo flags like -u/-S) is
    # accepted, so the elevated program is still exactly one of the 6
    # authorized tools, never sudo doing something else.
    program_idx = 0
    if tokens[0].lower() == "sudo":
        if len(tokens) < 2:
            return False, "`sudo` with no command.", []
        program_idx = 1

    program = tokens[program_idx]
    if program.lower() not in ALLOWED_PROGRAMS:
        return False, f"Program not allowed: {program}", []

    return True, "", tokens
