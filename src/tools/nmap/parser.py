"""
Nmap Parser — turns raw nmap console output into structured data.

Parser layer only; never executes commands, never touches GUI, never calls
AI (docs/Resource System.md #10, #14).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
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


def parse_nmap_xml(path: str) -> List[Dict]:
    """
    Parse a real nmap `-oX` output file into structured per-host data for
    the Zenmap-style Results Display tab (`src.ui.widgets.ResultsDisplayTab
    .set_hosts()`). Returns [] on any read/parse failure — degrade quietly,
    never crash the caller.
    """
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return []

    hosts: List[Dict] = []
    for host_el in root.findall("host"):
        status_el = host_el.find("status")
        state = status_el.get("state", "unknown") if status_el is not None else "unknown"

        ip, mac = "-", "-"
        for addr_el in host_el.findall("address"):
            addrtype = addr_el.get("addrtype", "")
            if addrtype in ("ipv4", "ipv6"):
                ip = addr_el.get("addr", "-")
            elif addrtype == "mac":
                mac = addr_el.get("addr", "-")

        hostname = "-"
        hostnames_el = host_el.find("hostnames")
        if hostnames_el is not None:
            hn_el = hostnames_el.find("hostname")
            if hn_el is not None:
                hostname = f"{hn_el.get('name', '-')} - {hn_el.get('type', '-')}"

        os_name, accuracy = "-", 0
        os_el = host_el.find("os")
        if os_el is not None:
            osmatch_el = os_el.find("osmatch")
            if osmatch_el is not None:
                os_name = osmatch_el.get("name", "-")
                accuracy = int(osmatch_el.get("accuracy", "0") or 0)

        uptime, lastboot = "Not available", "Not available"
        uptime_el = host_el.find("uptime")
        if uptime_el is not None:
            seconds = uptime_el.get("seconds")
            if seconds:
                uptime = f"{seconds} seconds"
            lastboot = uptime_el.get("lastboot", "Not available")

        ports: List[Dict] = []
        open_c = filtered_c = closed_c = 0
        ports_el = host_el.find("ports")
        if ports_el is not None:
            for extra_el in ports_el.findall("extraports"):
                st = extra_el.get("state", "")
                cnt = int(extra_el.get("count", "0") or 0)
                if st == "open":
                    open_c += cnt
                elif st == "filtered":
                    filtered_c += cnt
                elif st == "closed":
                    closed_c += cnt
            for port_el in ports_el.findall("port"):
                pstate_el = port_el.find("state")
                pstate = pstate_el.get("state", "") if pstate_el is not None else ""
                service_el = port_el.find("service")
                service = service_el.get("name", "-") if service_el is not None else "-"
                ports.append({
                    "port": port_el.get("portid", ""),
                    "proto": port_el.get("protocol", ""),
                    "service": service,
                    "state": pstate,
                })
                if pstate == "open":
                    open_c += 1
                elif pstate == "filtered":
                    filtered_c += 1
                elif pstate == "closed":
                    closed_c += 1

        hosts.append({
            "host": hostname.split(" - ")[0] if hostname != "-" else ip,
            "state": state,
            "open": open_c,
            "filtered": filtered_c,
            "closed": closed_c,
            "scanned": open_c + filtered_c + closed_c,
            "uptime": uptime,
            "lastboot": lastboot,
            "ip": ip,
            "mac": mac,
            "hostname": hostname,
            "os": os_name,
            "accuracy": accuracy,
            "ports": ports,
        })
    return hosts
