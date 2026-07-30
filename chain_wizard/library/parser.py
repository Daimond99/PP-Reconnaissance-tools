"""
Parse scan output files (gnmap format) into structured ScanResult objects.
"""

import re
from core.models import ScanResult


def parse_gnmap(filepath: str) -> list[ScanResult]:
    """
    Parse a .gnmap file produced by nmap -oG or masscan -oG.
    Returns a list of ScanResult (port, service).

    Expected line format:
      Host: 192.168.1.1 ()  Ports: 22/open/tcp//ssh//...
    """
    results: list[ScanResult] = []
    pattern = re.compile(r"(\d+)/(open)/tcp//([^/]*)")

    try:
        with open(filepath) as f:
            for line in f:
                if not line.startswith("Host:") or "Ports:" not in line:
                    continue
                _, ports_part = line.split("Ports:", 1)
                for match in pattern.finditer(ports_part):
                    port = int(match.group(1))
                    service = match.group(3).strip()
                    results.append(ScanResult(port=port, service=service))
    except FileNotFoundError:
        pass  # caller should handle empty result

    return results