"""
Nmap Analyzer — risk/impact evaluation for the Human Confirmation Gate.
Analysis never modifies execution results (docs/ARCHITECTURE.md, Analysis Layer).
"""

from __future__ import annotations

import ipaddress
from typing import List, Optional, Tuple

from src.utils.resource_loader import load_json

_SUBNET_HOST_ESTIMATE = {
    "8": 16777214, "16": 65534, "24": 254, "28": 14, "30": 2,
}

# One flag_impacts.json per authorized tool (src/resources/<tool>/) — same
# resource-driven pattern nmap already used, extended to the other 5 so the
# Confirmation Gate can show a real per-flag warning no matter which tool's
# command is being confirmed, not just nmap's.
_FLAG_IMPACT_FILES = {
    "nmap": "nmap/flag_impacts.json",
    "masscan": "masscan/flag_impacts.json",
    "ncat": "ncat/flag_impacts.json",
    "hydra": "hydra/flag_impacts.json",
    "ncrack": "ncrack/flag_impacts.json",
    "evil-winrm": "evil-winrm/flag_impacts.json",
}


def _flag_impact_map(tool: str) -> dict:
    return load_json(_FLAG_IMPACT_FILES.get(tool, _FLAG_IMPACT_FILES["nmap"]))


def _estimate_host_count(target: str) -> Optional[int]:
    """Rough estimate of how many hosts a target expression covers."""
    if "/" in target:
        try:
            prefix = target.split("/", 1)[1]
            return _SUBNET_HOST_ESTIMATE.get(prefix) or max(2 ** (32 - int(prefix)) - 2, 1)
        except (ValueError, IndexError):
            return None
    if "-" in target and target.count(".") == 3:
        try:
            last_octet = target.rsplit(".", 1)[1]
            start, end = last_octet.split("-")
            return int(end) - int(start) + 1
        except ValueError:
            return None
    return 1


# Tools that actually send scan probes at a target (vs. hydra/ncrack login
# attempts, ncat connections, evil-winrm sessions — those get their own
# specific warning via `extra_impact`, so the generic "sends packets" note
# would just be noise repeated on every single confirmation box).
_SCAN_TOOLS = {"nmap", "masscan"}


def generate_impact_description(flags: List[str], target: str, tool: str = "nmap") -> str:
    """Plain-language, one-thing-per-line summary of what a command will do,
    for the confirmation gate. Kept short on purpose: only flags that
    actually change behavior are listed, and only scan tools get the
    generic "sends real traffic" reminder — everything else is redundant
    with the Target line already shown in the box.

    `tool` picks which flag_impacts.json to read (defaults to nmap for
    backward compatibility with existing callers) — each of the 6
    authorized tools has its own flag vocabulary."""
    flag_impact = _flag_impact_map(tool)
    bullets: List[str] = []

    host_count = _estimate_host_count(target)
    if host_count and host_count > 1:
        bullets.append(f"This hits about {host_count} computers (a range), not just one")

    idx = 0
    seen_flags: List[str] = []
    while idx < len(flags):
        token = flags[idx]
        if token in flag_impact:
            seen_flags.append(token)
            desc = flag_impact[token]
            if token == "--script" and idx + 1 < len(flags):
                desc += f" (script: {flags[idx + 1]})"
                idx += 1
            bullets.append(f"{token} — {desc}")
        idx += 1

    if "-A" in seen_flags or "-O" in seen_flags:
        bullets.append("Easy for the target's security tools to notice")

    if tool in _SCAN_TOOLS:
        bullets.append("Sends real traffic to the target — it may show up in the target's own logs")

    if not bullets:
        bullets.append("Nothing risky here — a plain run against the target above")

    return "\n".join(bullets)


# Short meanings for the nmap options the wizard and warheads actually use.
_FLAG_NOTES = {
    "-sS": "SYN scan", "-sT": "full TCP connect", "-sU": "UDP scan",
    "-sV": "detect versions", "-sC": "default scripts", "-sn": "ping only",
    "-Pn": "skip ping", "-O": "detect OS", "-A": "OS + versions + scripts",
    "-F": "fast, top 100", "-f": "split packets", "-oG": "grey output file",
    "-oX": "XML output file", "-oN": "normal output file",
    "-T0": "slowest timing", "-T1": "slow timing", "-T2": "polite timing",
    "-T3": "normal timing", "-T4": "fast timing", "-T5": "fastest timing",
}


def _explain_flags(command: str) -> str:
    """One readable line of what the known options in `command` mean."""
    parts = command.split()
    notes = []
    for i, tok in enumerate(parts):
        if tok in _FLAG_NOTES:
            notes.append(f"{tok} {_FLAG_NOTES[tok]}")
        elif tok == "--top-ports" and i + 1 < len(parts):
            notes.append(f"--top-ports {parts[i + 1]} = top {parts[i + 1]} ports")
        elif tok == "-p" and i + 1 < len(parts):
            notes.append(f"-p {parts[i + 1]} = these ports")
        elif tok == "--script" and i + 1 < len(parts):
            notes.append(f"--script {parts[i + 1]} = run scripts")
    return " · ".join(notes)


def _script_warning(command: str) -> str:
    """Warning shown when an nmap command runs NSE scripts (--script or -sC)."""
    parts = command.split()
    if "--script" in parts or "-sC" in parts:
        return ("Runs NSE scripts. Some send attack-like requests and can crash "
                "weak services. Only run them on systems you are allowed to test.")
    return ""


def _noise_level(command: str) -> str:
    """Rough 'how easy is this to notice' rating from the options used.
    Heuristic only: fast timing, many ports, OS/script probes and vuln scripts
    make a scan louder; slow timing and few ports keep it quiet."""
    parts = command.split()
    score = 0
    if any(t in ("-T4", "-T5") for t in parts):
        score += 1
    if any(t in ("-A", "-O", "-sC") for t in parts) or "--script" in parts:
        score += 1
    if "-p-" in parts or "-sU" in parts or any(
            parts[i] == "--top-ports" and i + 1 < len(parts) and parts[i + 1].isdigit()
            and int(parts[i + 1]) >= 1000 for i in range(len(parts))):
        score += 1
    if any(t in ("-T0", "-T1", "-T2", "-F") for t in parts):
        score -= 1
    if score <= 0:
        return "LOW - few packets, unlikely to stand out"
    if score == 1:
        return "MEDIUM - visible in target logs"
    return "HIGH - easy to notice, may trigger alerts"


def format_confirmation_box(command: str, target: str, impact: str) -> str:
    """Short preview for a human: tool, target, what it does, the command, and
    what its options mean."""
    words = [w for w in command.split() if w != "sudo"]
    tool = words[0] if words else "?"
    what = " ".join(line.strip() for line in impact.splitlines() if line.strip())
    flags = _explain_flags(command)
    warning = _script_warning(command)
    lines = [
        "COMMAND PREVIEW",
        "────────────────────────────────────────",
        f" Tool    : {tool}",
        f" Target  : {target}",
        f" Does    : {what}",
        f" Command : {command}",
    ]
    if flags:
        lines.append(f" Flags   : {flags}")
    lines.append(f" Impact  : {_noise_level(command)}")
    if warning:
        lines.append(f" Warning : {warning}")
    lines += [
        "────────────────────────────────────────",
        " Run = execute   |   Skip / No = cancel",
    ]
    return "\n".join(lines)


def is_target_in_scope(target: str, scope: str) -> Tuple[bool, str]:
    """
    Check that `target` falls inside the authorized `scope` CIDR.
    Hostnames and IP ranges (e.g. 192.168.1.10-20) can't be checked as
    CIDR membership, so they're passed through — the confirmation box
    still forces an explicit human scope acknowledgement before execution.
    """
    target = (target or "").strip()
    if not target:
        return False, "Target is empty"

    try:
        scope_net = ipaddress.ip_network(scope, strict=False)
    except ValueError:
        return False, f"Configured scope is invalid: {scope}"

    try:
        if "/" in target:
            target_net = ipaddress.ip_network(target, strict=False)
            if target_net.subnet_of(scope_net):
                return True, ""
            return False, f"{target} is outside the authorized scope ({scope})"
        if target.count(".") == 3 and "-" not in target.rsplit(".", 1)[-1]:
            if ipaddress.ip_address(target) in scope_net:
                return True, ""
            return False, f"{target} is outside the authorized scope ({scope})"
    except ValueError:
        pass  # hostname or IP-range expression — allow through to the human gate

    return True, ""
