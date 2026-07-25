"""
Wizard input validation and safe command assembly.
Prevents shell metacharacter injection before QProcess execution.
"""

import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

AUTHORIZED_SCOPE_WARNING = (
    "⚠ AUTHORIZED USE ONLY — Run scans only against targets within your approved scope."
)

# ---------------------------------------------------------------------------
# Impact descriptions (Human Confirmation Gate)
# ---------------------------------------------------------------------------
# Maps individual nmap flags/tokens to a plain-language Thai description of
# what running that flag actually does. Used to auto-generate the "Impact"
# line shown in the confirmation box before anything executes.

NMAP_FLAG_IMPACT: Dict[str, str] = {
    "-sS": "ใช้ TCP SYN scan (stealth scan กึ่งเปิดการเชื่อมต่อ)",
    "-sT": "ใช้ TCP Connect scan (เปิดการเชื่อมต่อเต็มรูปแบบ เห็นชัดใน log ปลายทางมากกว่า -sS)",
    "-sU": "สแกน UDP port เพิ่มเติม ใช้เวลานานกว่า TCP scan มาก",
    "-sV": "พยายามระบุเวอร์ชันของ service ที่รันอยู่บนแต่ละ port (ส่ง probe เพิ่มเติม)",
    "-sC": "รันชุด default NSE scripts เพื่อดึงข้อมูลเพิ่มเติมจาก service",
    "-A": "เปิดโหมด Aggressive (OS detection + version detection + script scan + traceroute) มี footprint สูงและถูกตรวจจับได้ง่าย",
    "-O": "พยายามระบุระบบปฏิบัติการของเป้าหมาย (intrusive กว่าการสแกน service ธรรมดา)",
    "-Pn": "ข้ามขั้นตอน host discovery (ping) แล้วสแกนทุก IP ราวกับ online เสมอ อาจเพิ่มเวลาที่ใช้",
    "-n": "ข้ามการ resolve DNS ทำให้สแกนเร็วขึ้นเล็กน้อย",
    "-F": "สแกนเฉพาะ 100 port ที่พบบ่อย (เร็วกว่าการสแกนทุก port)",
    "-f": "แบ่ง fragment packet ออกเป็นชิ้นเล็ก ๆ เพื่อหลบหลีก firewall/IDS พื้นฐานที่ตรวจสอบเฉพาะ packet เต็ม",
    "--open": "แสดงเฉพาะ port ที่เปิดอยู่ในผลลัพธ์",
    "--script": "รัน NSE script ที่ระบุ ซึ่งอาจส่ง request เพิ่มเติมไปยังเป้าหมายตามชนิดของ script",
    "-T0": "ความเร็ว Paranoid — ช้ามาก หลีกเลี่ยงการตรวจจับโดย IDS ได้ดีที่สุด",
    "-T1": "ความเร็ว Sneaky — ช้า เน้นหลีกเลี่ยงการตรวจจับ",
    "-T2": "ความเร็ว Polite — ลด load บนเครือข่ายและเป้าหมาย",
    "-T3": "ความเร็วปกติ (default)",
    "-T4": "ความเร็ว Aggressive — เร็ว เหมาะกับเครือข่ายภายใน/lab อาจทำให้ IDS แจ้งเตือน",
    "-T5": "ความเร็ว Insane — เร็วที่สุด มีโอกาสพลาดผลลัพธ์และถูกตรวจจับสูงมาก",
    "-v": "เพิ่มระดับ verbose แสดงผล progress และรายละเอียดระหว่างสแกนแบบ real-time",
    "--version-all": "พยายาม probe ทุก service probe เพื่อระบุเวอร์ชันให้ละเอียดที่สุด (ใช้เวลานานขึ้น)",
}

_SUBNET_HOST_ESTIMATE = {
    "8": 16777214, "16": 65534, "24": 254, "28": 14, "30": 2,
}


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


def generate_impact_description(flags: List[str], target: str) -> str:
    """Auto-generate a plain-language impact summary for the confirmation gate."""
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
        if token in NMAP_FLAG_IMPACT:
            seen_flags.append(token)
            desc = NMAP_FLAG_IMPACT[token]
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


import ipaddress


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


_LLM_AUDIT_LOG_PATH = Path("logs") / "llm_mode_audit_log.jsonl"


def audit_log_llm(channel: str, command: str, target: str, response: str,
                   executed: bool, provider: Optional[str] = None,
                   extra: Optional[Dict] = None) -> None:
    """
    Dedicated audit trail for LLM Mode (Plain + AI). Records which channel
    (plain/ai) and provider (openai/anthropic/None) were used for every
    confirmation decision — but NEVER the API key itself.
    Best-effort, never raises.
    """
    try:
        _LLM_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "provider": provider,
            "command": command,
            "target": target,
            "response": response,
            "executed": executed,
        }
        if extra:
            entry.update(extra)
        with _LLM_AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


_RECON_KEYWORDS = (
    # English
    "scan", "port", "nmap", "masscan", "service", "detect", "network",
    "host", "target", "vulnerab", "recon", "firewall", "subnet", "cidr",
    "ip ", "server", "os ",
    # Thai
    "สแกน", "พอร์ต", "เครือข่าย", "เป้าหมาย", "เซอร์วิส", "ช่องโหว่",
    "ระบบปฏิบัติการ", "ตรวจสอบ", "เปิด", "โฮสต์", "เซิร์ฟเวอร์",
)


def is_recon_related(user_input: str) -> bool:
    """
    Cheap client-side pre-filter, run BEFORE spending an AI Mode API call.
    Not a security boundary by itself (that's the system prompt + output
    validation) — just a keyword whitelist to catch obviously off-topic
    requests and warn the user before they burn API credit.
    """
    text = (user_input or "").lower()
    return any(keyword in text for keyword in _RECON_KEYWORDS)


_LLM_CMD_LINE_RE = re.compile(r"^(nmap|masscan)\b.*$", re.MULTILINE)


def validate_ai_response(text: str) -> Tuple[bool, str]:
    """
    Validate an LLM's raw response before it is ever treated as a command
    candidate.

    Returns (True, command) only when a real nmap/masscan command line is
    present AND passes the same program/flag whitelist used everywhere else
    (parse_command_line). Otherwise returns (False, raw_text) so the caller
    can display the model's reply as plain informational text — it must
    NEVER be forwarded to the Confirmation Gate or QProcess.
    """
    raw = (text or "").strip()
    match = _LLM_CMD_LINE_RE.search(raw)
    if not match:
        return False, raw or "(no output)"

    candidate = match.group(0).strip()
    ok, _err, _argv = parse_command_line(candidate)
    if not ok:
        return False, raw
    return True, candidate


_AUDIT_LOG_PATH = Path("logs") / "wizard_audit_log.jsonl"


def audit_log_confirmation(command: str, target: str, response: str, executed: bool) -> None:
    """Append a confirmation decision to the audit log (best-effort, never raises)."""
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "target": target,
            "response": response,
            "executed": executed,
        }
        with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Audit logging must never block or crash the wizard flow.
        pass


def audit_log_fallback(
    *, target: str, step: str, rejected_tool: str, fallback_tool: str,
    detected_ports: List[int], reason: str,
) -> None:
    """Record an Auto Chain fallback decision without exposing credentials."""
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "auto_chain_fallback",
            "target": target,
            "step": step,
            "rejected_tool": rejected_tool,
            "fallback_tool": fallback_tool,
            "detected_ports": sorted(set(detected_ports)),
            "reason": reason,
        }
        with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def audit_log_cancel(command: str, target: str, reason: str = "user_cancelled") -> None:
    """Append a cancellation event to the audit log (best-effort, never raises)."""
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "cancel",
            "command": command,
            "target": target,
            "reason": reason,
        }
        with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

DANGEROUS_SHELL_CHARS = re.compile(r"[;|&`$()<>\\]")

TARGET_PATTERN = re.compile(
    r"^(?:"
    r"(?:\d{1,3}\.){3}\d{1,3}"  # IPv4
    r"|(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}"  # CIDR
    r"|(?:\d{1,3}\.){3}\d{1,3}-\d{1,3}"  # range suffix
    r"|[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"  # hostname
    r")$"
)

PORT_RANGE_PATTERN = re.compile(
    r"^(?:\d{1,5}(?:-\d{1,5})?)(?:,\d{1,5}(?:-\d{1,5})?)*$"
)

PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_./\\:\-]+$")

NMAP_FLAG_WHITELIST = {
    "-F", "-sS", "-sT", "-sU", "-sV", "-sC", "-A", "-O", "-Pn", "-n",
    "-p", "-T0", "-T1", "-T2", "-T3", "-T4", "-T5",
    "-f", "-v",
    "--open", "--script", "--version-all", "-oN", "-oX", "-oG",
}

NMAP_SCRIPT_WHITELIST = re.compile(
    r"^[a-z0-9,\-*]+(?:/[a-z0-9,\-*]+)*$"
)

YES_NO = {"y", "yes", "n", "no"}


def validate_exact_confirmation(value: str) -> bool:
    """Only the literal string 'yes' (case-sensitive) counts as confirmation.
    Anything else — including 'y', 'Yes', empty Enter, or 'no' — cancels."""
    return value == "yes"


def validate_yes_no(value: str) -> Tuple[bool, Optional[bool], str]:
    """Return (ok, is_yes_or_no, error_message)."""
    normalized = value.strip().lower()
    if normalized in ("y", "yes"):
        return True, True, ""
    if normalized in ("n", "no"):
        return True, False, ""
    return False, None, "Please answer y or n."


def validate_target(value: str) -> Tuple[bool, str]:
    target = value.strip()
    if not target:
        return False, "Target cannot be empty."
    if DANGEROUS_SHELL_CHARS.search(target):
        return False, "Target contains disallowed characters (;|&`$()<>\\)."
    if not TARGET_PATTERN.match(target):
        return False, "Invalid target format. Use IP, CIDR, hostname, or range."
    return True, target


def validate_port_range(value: str) -> Tuple[bool, str]:
    ports = value.strip()
    if not ports:
        return False, "Port range cannot be empty."
    if DANGEROUS_SHELL_CHARS.search(ports):
        return False, "Port range contains disallowed characters."
    if not PORT_RANGE_PATTERN.match(ports):
        return False, "Invalid port range. Example: 22 or 22,80,443 or 1-1024."
    for part in ports.replace(",", "-").split("-"):
        if part.isdigit() and not (1 <= int(part) <= 65535):
            return False, f"Port {part} out of range (1-65535)."
    return True, ports


def validate_file_path(value: str) -> Tuple[bool, str]:
    path = value.strip().strip('"').strip("'")
    if not path:
        return False, "Path cannot be empty."
    if DANGEROUS_SHELL_CHARS.search(path):
        return False, "Path contains disallowed characters."
    if not PATH_PATTERN.match(path):
        return False, "Path contains invalid characters."
    return True, path


def validate_url(value: str) -> Tuple[bool, str]:
    url = value.strip()
    if not url:
        return False, "URL cannot be empty."
    if DANGEROUS_SHELL_CHARS.search(url):
        return False, "URL contains disallowed characters."
    if not re.match(r"^https?://[a-zA-Z0-9.\-:/_%]+$", url):
        return False, "Invalid URL. Example: http://192.168.1.1"
    return True, url


def validate_username(value: str) -> Tuple[bool, str]:
    user = value.strip()
    if not user:
        return False, "Username cannot be empty."
    if not re.match(r"^[a-zA-Z0-9._@\-\\]+$", user):
        return False, "Username contains invalid characters."
    return True, user


def validate_password(value: str) -> Tuple[bool, str]:
    if not value:
        return False, "Password cannot be empty."
    if DANGEROUS_SHELL_CHARS.search(value):
        return False, "Password contains disallowed shell characters."
    return True, value


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


def quote_arg(value: str) -> str:
    """Quote argument for display; shlex.split reverses on execution."""
    return shlex.quote(value)


def build_nmap_command(flags: List[str], target: str) -> str:
    parts = ["nmap", *flags, target]
    return " ".join(quote_arg(p) for p in parts)


def parse_command_line(command: str) -> Tuple[bool, str, List[str]]:
    """
    Parse a full command string into [program, arg1, arg2, ...].
    Returns (ok, error_message, argv).
    """
    command = command.strip()
    if not command:
        return False, "Empty command.", []

    if DANGEROUS_SHELL_CHARS.search(command):
        return False, "Command contains disallowed shell metacharacters.", []

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return False, f"Could not parse command: {exc}", []

    if not tokens:
        return False, "Empty command.", []

    program = tokens[0]
    allowed_programs = {
        "nmap", "masscan", "hydra", "ncrack", "ncat",
        "evil-winrm", "gobuster", "dirb",
    }
    if program.lower() not in allowed_programs:
        return False, f"Program not allowed: {program}", []

    return True, "", tokens


def split_command_chain(chain: str) -> Tuple[bool, str, List[str]]:
    """Split 'cmd1 && cmd2' into individual command strings."""
    if "&&" not in chain:
        ok, err, _ = parse_command_line(chain)
        return (ok, err, [chain.strip()]) if ok else (False, err, [])

    parts = [part.strip() for part in chain.split("&&")]
    for part in parts:
        ok, err, _ = parse_command_line(part)
        if not ok:
            return False, err, []
    return True, "", parts
