"""
Generic, tool-agnostic input validation.

Validators only validate — they never build or execute commands
(docs/Resource System.md #10, "Validators never generate commands").
"""

from __future__ import annotations

import re
import shlex
from typing import List, Tuple

DANGEROUS_SHELL_CHARS = re.compile(r"[;|&`$()<>\\]")

# Programs any generated/AI-suggested command line is allowed to invoke.
ALLOWED_PROGRAMS = {
    "nmap", "masscan", "hydra", "ncrack", "ncat",
    "evil-winrm", "gobuster", "dirb",
}


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

    if DANGEROUS_SHELL_CHARS.search(command):
        return False, "Command contains disallowed shell metacharacters.", []

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return False, f"Could not parse command: {exc}", []

    if not tokens:
        return False, "Empty command.", []

    program = tokens[0]
    if program.lower() not in ALLOWED_PROGRAMS:
        return False, f"Program not allowed: {program}", []

    return True, "", tokens
