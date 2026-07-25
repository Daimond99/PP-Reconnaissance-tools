"""
Nmap Parser — turns raw nmap console output into structured data.

Parser layer only; never executes commands, never touches GUI, never calls
AI (docs/Resource System.md #10, #14).
"""

from __future__ import annotations

import re
from typing import Dict, List

_PORT_LINE_RE = re.compile(r"^(\d+)/(tcp|udp)\s+(\S+)(?:\s+(\S+))?", re.MULTILINE)


def parse_open_ports(output: str) -> List[Dict[str, str]]:
    """
    Parse classic nmap console output (not XML) and return open ports.

    Each item: {"port": str, "protocol": str, "state": str, "service": str}
    """
    ports: List[Dict[str, str]] = []
    for match in _PORT_LINE_RE.finditer(output):
        port, protocol, state, service = match.groups()
        if state != "open":
            continue
        ports.append(
            {
                "port": port,
                "protocol": protocol,
                "state": state,
                "service": service or "",
            }
        )
    return ports


def count_open_ports(output: str) -> int:
    return len(parse_open_ports(output))
