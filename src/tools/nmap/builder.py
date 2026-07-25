"""
Nmap Command Builder — converts validated flags/target into an executable
command string. Builders never execute commands (docs/Wizard Engine
Architecture.md #18.3).
"""

from __future__ import annotations

import shlex
from typing import List


def quote_arg(value: str) -> str:
    """Quote argument for display; shlex.split reverses on execution."""
    return shlex.quote(value)


def build_nmap_command(flags: List[str], target: str) -> str:
    parts = ["nmap", *flags, target]
    return " ".join(quote_arg(p) for p in parts)
