"""
Ncrack Parser — turns a completed ncrack run's `-oN` (normal) output into
structured credential rows for the Results Display "Credentials Found" view.

Parser layer only; never executes commands, never touches GUI.
"""

from __future__ import annotations

import re
from typing import Dict, List

# Ncrack's discovered-credential line in -oN (Normal) output:
#   Discovered credentials for ssh on 192.168.1.50 22/tcp:
#   192.168.1.50 22/tcp ssh: 'admin' 'toor'
_LINE_RE = re.compile(
    r"^(?P<host>\S+)\s+(?P<port>\d+)/(?P<proto>\w+)\s+(?P<service>\S+):"
    r"\s+'(?P<login>[^']*)'\s+'(?P<password>[^']*)'\s*$"
)


def parse_ncrack_output(path: str) -> List[Dict]:
    """
    Parse an ncrack `-oN` output file into a list of
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
