"""Tests for src/validation/common.py — the shared safety validators that
gate every command before it can be built or run.

These are the load-bearing checks: the 6-tool whitelist, the quote-aware
shell-injection guard, the exact-"yes" confirmation rule, and the Windows→WSL
path rewrite. If any of these regress, the confirmation gate is unsafe.
"""

from __future__ import annotations

import pytest

from src.validation.common import (
    convert_windows_paths_to_wsl,
    parse_command_line,
    validate_exact_confirmation,
    _has_unquoted_shell_metachar,
)


# --------------------------------------------------------------------------
# parse_command_line — whitelist + injection guard
# --------------------------------------------------------------------------

class TestParseCommandLineAllowed:
    @pytest.mark.parametrize("cmd", [
        "nmap -sV 192.168.1.10",
        "masscan -p1-65535 192.168.1.0/24",
        "hydra -l admin -P rockyou.txt 192.168.1.10 ssh",
        "ncrack -p 22 192.168.1.10",
        "ncat -lvnp 4444",
        "evil-winrm -i 192.168.1.10 -u admin -p pass",
    ])
    def test_each_authorized_tool_parses(self, cmd):
        ok, err, argv = parse_command_line(cmd)
        assert ok is True, err
        assert argv[0] == cmd.split()[0]

    def test_returns_full_argv(self):
        ok, _, argv = parse_command_line("nmap -sV -p80 192.168.1.10")
        assert ok
        assert argv == ["nmap", "-sV", "-p80", "192.168.1.10"]

    def test_quoted_metachar_payload_allowed(self):
        # hydra's http-post-form payload legitimately contains `&` and `=`
        # inside quotes — must NOT be rejected as injection.
        cmd = 'hydra 192.168.1.10 http-post-form "/login:user=^USER^&pass=^PASS^:F=fail"'
        ok, err, _ = parse_command_line(cmd)
        assert ok is True, err


class TestParseCommandLineRejected:
    def test_empty(self):
        ok, err, argv = parse_command_line("")
        assert ok is False
        assert argv == []

    def test_whitespace_only(self):
        ok, _, _ = parse_command_line("   ")
        assert ok is False

    def test_disallowed_program(self):
        ok, err, _ = parse_command_line("rm -rf /")
        assert ok is False
        assert "not allowed" in err.lower()

    @pytest.mark.parametrize("cmd", [
        "nmap -sV 192.168.1.10; rm -rf /",     # command chaining
        "nmap 192.168.1.10 | tee out",         # pipe
        "nmap 192.168.1.10 & sleep 5",         # background
        "nmap `id`",                            # backtick subshell
        "nmap $(id)",                           # $() subshell
        "nmap 192.168.1.10 > /etc/passwd",     # redirect
    ])
    def test_shell_injection_shapes_rejected(self, cmd):
        ok, err, _ = parse_command_line(cmd)
        assert ok is False
        assert "metacharacter" in err.lower()


class TestSudoHandling:
    def test_bare_sudo_prefix_allowed(self):
        ok, err, argv = parse_command_line("sudo masscan -p1-100 192.168.1.0/24")
        assert ok is True, err
        assert argv[:2] == ["sudo", "masscan"]

    def test_sudo_alone_rejected(self):
        ok, err, _ = parse_command_line("sudo")
        assert ok is False
        assert "no command" in err.lower()

    def test_sudo_with_flag_rejected(self):
        # `sudo -u root nmap ...` — the token after sudo is `-u`, not an
        # authorized tool, so it must be rejected (no sudo doing something
        # other than elevating one of the 6 tools).
        ok, err, _ = parse_command_line("sudo -u root nmap 192.168.1.10")
        assert ok is False
        assert "not allowed" in err.lower()


# --------------------------------------------------------------------------
# _has_unquoted_shell_metachar — the quote-aware scanner directly
# --------------------------------------------------------------------------

class TestUnquotedMetacharScanner:
    def test_bare_semicolon_flagged(self):
        assert _has_unquoted_shell_metachar("a; b") == ";"

    def test_metachar_inside_single_quotes_ok(self):
        assert _has_unquoted_shell_metachar("foo 'a;b|c' bar") is None

    def test_metachar_inside_double_quotes_ok(self):
        assert _has_unquoted_shell_metachar('foo "a&b=c" bar') is None

    def test_returns_first_offending_char(self):
        assert _has_unquoted_shell_metachar("clean | then ; more") == "|"

    def test_escaped_quote_inside_double_quotes(self):
        # backslash-escaped quote shouldn't prematurely close the region
        assert _has_unquoted_shell_metachar('"a\\"b&c"') is None


# --------------------------------------------------------------------------
# validate_exact_confirmation — only literal "yes"
# --------------------------------------------------------------------------

class TestExactConfirmation:
    def test_exact_yes_confirms(self):
        assert validate_exact_confirmation("yes") is True

    @pytest.mark.parametrize("value", ["y", "Yes", "YES", "no", "", "yes ", " yes", "yeah", "1"])
    def test_everything_else_cancels(self, value):
        assert validate_exact_confirmation(value) is False


# --------------------------------------------------------------------------
# convert_windows_paths_to_wsl
# --------------------------------------------------------------------------

class TestWindowsPathConversion:
    def test_bare_c_drive_path(self):
        out = convert_windows_paths_to_wsl(r"hydra -P C:\Users\me\rockyou.txt 192.168.1.10 ssh")
        assert "/mnt/c/Users/me/rockyou.txt" in out
        assert "C:\\" not in out

    def test_lowercase_drive_letter(self):
        out = convert_windows_paths_to_wsl(r"nmap -oX d:\scans\out.xml 192.168.1.10")
        assert "/mnt/d/scans/out.xml" in out

    def test_quoted_path_with_space_preserved(self):
        out = convert_windows_paths_to_wsl(r'hydra -P "C:\word lists\rockyou.txt" t ssh')
        assert '"/mnt/c/word lists/rockyou.txt"' in out

    def test_command_without_drive_path_unchanged(self):
        cmd = "nmap -sV 192.168.1.10"
        assert convert_windows_paths_to_wsl(cmd) == cmd
