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


def generate_impact_description(flags: List[str], target: str, tool: str = "nmap") -> str:
    """Auto-generate a plain-language impact summary for the confirmation gate.

    `tool` picks which flag_impacts.json to read (defaults to nmap for
    backward compatibility with existing callers) — each of the 6
    authorized tools has its own flag vocabulary."""
    flag_impact = _flag_impact_map(tool)
    notes: List[str] = []

    host_count = _estimate_host_count(target)
    if host_count and host_count > 1:
        notes.append(f"จะทำการสแกนเป้าหมายทั้งหมดประมาณ {host_count} host ในช่วง {target}")
    else:
        notes.append(f"จะทำการสแกนเป้าหมายเดียว: {target}")

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
            notes.append(f"[{token}] {desc}")
        idx += 1

    if "-A" in seen_flags or "-O" in seen_flags:
        notes.append("[!] คำสั่งนี้จัดว่า intrusive — มีโอกาสถูกตรวจจับโดย IDS/IPS สูงกว่าปกติ")

    notes.append(
        "มีการส่ง packet ออกไปยังเครื่องปลายทางจริง อาจถูกตรวจจับหรือบันทึกโดยระบบเฝ้าระวังของเป้าหมาย"
    )
    return "\n              ".join(notes)


def format_confirmation_box(command: str, target: str, impact: str) -> str:
    """Render the Human Confirmation Gate preview box."""
    return (
        "─────────────────────────────────────────\n"
        " COMMAND PREVIEW\n"
        f" Command : {command}\n"
        f" Target  : {target}\n"
        f" Impact  : {impact}\n"
        " Scope Check : ยืนยันว่า target อยู่ในขอบเขตที่ได้รับอนุญาต (sandbox/lab) แล้ว?\n"
        "─────────────────────────────────────────\n"
        ' พิมพ์ "yes" เพื่อยืนยันและรันคำสั่ง หรือ "no" เพื่อยกเลิกและกลับไปแก้ไข'
    )


def is_target_in_scope(target: str, scope: str) -> Tuple[bool, str]:
    """
    Check that `target` falls inside the authorized `scope` CIDR.
    Hostnames and IP ranges (e.g. 192.168.1.10-20) can't be checked as
    CIDR membership, so they're passed through — the confirmation box
    still forces an explicit human scope acknowledgement before execution.
    """
    target = (target or "").strip()
    if not target:
        return False, "Target ว่างเปล่า"

    try:
        scope_net = ipaddress.ip_network(scope, strict=False)
    except ValueError:
        return False, f"Scope ที่ตั้งค่าไว้ไม่ถูกต้อง: {scope}"

    try:
        if "/" in target:
            target_net = ipaddress.ip_network(target, strict=False)
            if target_net.subnet_of(scope_net):
                return True, ""
            return False, f"{target} อยู่นอกขอบเขตที่ได้รับอนุญาต ({scope})"
        if target.count(".") == 3 and "-" not in target.rsplit(".", 1)[-1]:
            if ipaddress.ip_address(target) in scope_net:
                return True, ""
            return False, f"{target} อยู่นอกขอบเขตที่ได้รับอนุญาต ({scope})"
    except ValueError:
        pass  # hostname or IP-range expression — allow through to the human gate

    return True, ""
