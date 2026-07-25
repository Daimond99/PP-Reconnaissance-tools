"""
Hydra input validation — validates brute-force inputs before a command is
built. Validators never generate commands (docs/Resource System.md #10).

Reuses the shared, tool-agnostic validators in src/validation/common.py for
target / username / password / port / file-path checks and adds only the
hydra-specific service-module whitelist on top.
"""

from __future__ import annotations

from typing import Tuple

from src.validation.common import (
    DANGEROUS_SHELL_CHARS,
    validate_file_path,
    validate_password,
    validate_port_range,
    validate_target,
    validate_username,
)

# Service modules the wizard is allowed to hand to hydra. Kept deliberately
# small — matches the services the nmap->hydra chain maps to
# (src/resources/nmap/service_tools.json).
HYDRA_SERVICE_WHITELIST = {
    "ftp", "ssh", "telnet", "smtp", "http-get", "https-get",
    "http-post-form", "https-post-form", "mysql", "mssql",
    "postgres", "rdp", "smb", "vnc", "http-head",
}

_EXTRA_LETTERS = set("nsr")


def validate_service(value: str) -> Tuple[bool, str]:
    service = (value or "").strip().lower()
    if not service:
        return False, "Service cannot be empty."
    if service not in HYDRA_SERVICE_WHITELIST:
        return False, f"Service not allowed: {service}"
    return True, service


def validate_login_field(value: str) -> Tuple[bool, str, bool]:
    """A single username or a path to a userlist. Returns (ok, value, is_file)."""
    raw = (value or "").strip()
    if not raw:
        return False, "Login/userlist cannot be empty.", False
    # Treat anything containing a path separator as a file path.
    if "/" in raw or "\\" in raw:
        ok, msg = validate_file_path(raw)
        return ok, msg, ok
    ok, msg = validate_username(raw)
    return ok, msg, False


def validate_password_field(value: str) -> Tuple[bool, str, bool]:
    """A single password or a path to a passlist. Returns (ok, value, is_file)."""
    raw = value or ""
    if not raw.strip():
        return False, "Password/passlist cannot be empty.", False
    if "/" in raw or "\\" in raw:
        ok, msg = validate_file_path(raw.strip())
        return ok, msg, ok
    ok, msg = validate_password(raw)
    return ok, msg, False


def validate_extra(value: str) -> Tuple[bool, str]:
    """Letters for hydra -e: n (null), s (same as login), r (reversed)."""
    letters = (value or "").strip().lower()
    if not letters:
        return True, ""
    if DANGEROUS_SHELL_CHARS.search(letters):
        return False, "Invalid characters in extra options."
    if not set(letters) <= _EXTRA_LETTERS:
        return False, "Extra options may only contain the letters n, s, r."
    return True, letters


def validate_hydra_target(value: str) -> Tuple[bool, str]:
    return validate_target(value)


def validate_hydra_port(value: str) -> Tuple[bool, str]:
    port = (value or "").strip()
    if not port:
        return True, ""  # optional; hydra uses the service default
    return validate_port_range(port)
