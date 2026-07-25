"""
Generic, tool-agnostic input validation.

Validators only validate — they never build or execute commands
(docs/Resource System.md #10, "Validators never generate commands").
"""

from __future__ import annotations

import re
import shlex
from typing import Dict, List, Optional, Tuple

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

YES_NO = {"y", "yes", "n", "no"}

# Programs any generated/AI-suggested command line is allowed to invoke.
ALLOWED_PROGRAMS = {
    "nmap", "masscan", "hydra", "ncrack", "ncat",
    "evil-winrm", "gobuster", "dirb",
}

_RECON_KEYWORDS = (
    # English
    "scan", "port", "nmap", "masscan", "service", "detect", "network",
    "host", "target", "vulnerab", "recon", "firewall", "subnet", "cidr",
    "ip ", "server", "os ",
    # Thai
    "สแกน", "พอร์ต", "เครือข่าย", "เป้าหมาย", "เซอร์วิส", "ช่องโหว่",
    "ระบบปฏิบัติการ", "ตรวจสอบ", "เปิด", "โฮสต์", "เซิร์ฟเวอร์",
)

_LLM_CMD_LINE_RE = re.compile(r"^(nmap|masscan)\b.*$", re.MULTILINE)


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


def parse_command_line(command: str) -> Tuple[bool, str, List[str]]:
    """
    Parse a full command string into [program, arg1, arg2, ...] and check
    the program against the allow-list. Returns (ok, error_message, argv).
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
    if program.lower() not in ALLOWED_PROGRAMS:
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


def is_recon_related(user_input: str) -> bool:
    """
    Cheap client-side pre-filter, run BEFORE spending an AI Mode API call.
    Not a security boundary by itself (that's the system prompt + output
    validation) — just a keyword whitelist to catch obviously off-topic
    requests and warn the user before they burn API credit.
    """
    text = (user_input or "").lower()
    return any(keyword in text for keyword in _RECON_KEYWORDS)


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
