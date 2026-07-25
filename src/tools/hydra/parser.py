"""
Hydra Parser — turns raw hydra console output into structured results.

Parser layer only; never executes commands, never touches the GUI, never calls
AI (docs/Resource System.md #10, #14).
"""

from __future__ import annotations

import re
from typing import Dict, List

# Hydra prints each found credential like:
#   [22][ssh] host: 192.168.1.50   login: admin   password: secret
_CRED_RE = re.compile(
    r"\[(\d+)\]\[([^\]]+)\]\s+host:\s*(\S+)"
    r"(?:\s+login:\s*(\S+))?"
    r"(?:\s+password:\s*(\S+))?",
    re.IGNORECASE,
)

# Summary line: "1 valid password found" / "0 valid passwords found"
_SUMMARY_RE = re.compile(r"(\d+)\s+valid\s+passwords?\s+found", re.IGNORECASE)


def parse_hydra_results(output: str) -> List[Dict[str, str]]:
    """Return every credential hydra reported as found.

    Each item: {"port","service","host","login","password"}
    """
    creds: List[Dict[str, str]] = []
    for m in _CRED_RE.finditer(output):
        port, service, host, login, password = m.groups()
        creds.append(
            {
                "port": port,
                "service": service,
                "host": host,
                "login": login or "",
                "password": password or "",
            }
        )
    return creds


def count_valid_credentials(output: str) -> int:
    """Prefer hydra's own summary count; fall back to counting parsed lines."""
    m = _SUMMARY_RE.search(output)
    if m:
        return int(m.group(1))
    return len(parse_hydra_results(output))
