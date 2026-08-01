"""
Hydra Parser — turns a completed hydra run's `-o <file>` output into
structured credential rows for the Results Display "Credentials Found" view.

Parser layer only; never executes commands, never touches GUI.
"""

from __future__ import annotations

import re
from typing import Dict, List

# Hydra's found-credential line, both on the console and in a plain -o file:
#   [22][ssh] host: 192.168.1.50   login: admin   password: toor
_LINE_RE = re.compile(
    r"^\[(?P<port>\d+)\]\[(?P<service>\S+)\]\s+host:\s+(?P<host>\S+)"
    r"\s+login:\s+(?P<login>\S+)\s+password:\s+(?P<password>.+?)\s*$"
)


def parse_hydra_output(path: str) -> List[Dict]:
    """
    Parse a hydra `-o` output file into a list of
    {host, port, service, login, password} dicts. Returns [] on any
    read failure or if no credential lines are found — degrade quietly,
    never crash the caller.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return []

    creds: List[Dict] = []
    for line in text.splitlines():
        m = _LINE_RE.match(line.strip())
        if not m:
            continue
        creds.append({
            "host": m.group("host"),
            "port": m.group("port"),
            "service": m.group("service"),
            "login": m.group("login"),
            "password": m.group("password"),
        })
    return creds
