"""
Nmap-specific input validation: custom flag whitelist.
Validators never generate commands (docs/Resource System.md #10).
"""

from __future__ import annotations

import re
import shlex
from typing import Tuple

from src.validation.common import DANGEROUS_SHELL_CHARS, validate_port_range

NMAP_FLAG_WHITELIST = {
    "-F", "-sS", "-sT", "-sU", "-sV", "-sC", "-A", "-O", "-Pn", "-n",
    "-p", "-T0", "-T1", "-T2", "-T3", "-T4", "-T5",
    "-f", "-v",
    "--open", "--script", "--version-all", "-oN", "-oX", "-oG",
}

NMAP_SCRIPT_WHITELIST = re.compile(
    r"^[a-z0-9,\-*]+(?:/[a-z0-9,\-*]+)*$"
)


def validate_custom_nmap_flags(value: str) -> Tuple[bool, str]:
    flags = value.strip()
    if not flags:
        return False, "Nmap flags cannot be empty."
    if DANGEROUS_SHELL_CHARS.search(flags):
        return False, "Flags must not contain ; | & ` $ ( ) < > \\"

    try:
        tokens = shlex.split(flags)
    except ValueError as exc:
        return False, f"Invalid flag syntax: {exc}"

    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token.startswith("-") and token not in NMAP_FLAG_WHITELIST:
            return False, f"Flag not allowed: {token}"
        if token == "--script":
            if idx + 1 >= len(tokens):
                return False, "--script requires a script name."
            script = tokens[idx + 1]
            if not NMAP_SCRIPT_WHITELIST.match(script):
                return False, f"Script name not allowed: {script}"
            idx += 2
            continue
        if token == "-p":
            if idx + 1 >= len(tokens):
                return False, "-p requires a port specification."
            ok, _ = validate_port_range(tokens[idx + 1])
            if not ok:
                return False, f"Invalid ports for -p: {tokens[idx + 1]}"
            idx += 2
            continue
        idx += 1

    return True, flags
