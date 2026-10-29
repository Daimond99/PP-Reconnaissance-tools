"""Injection guard: a command line that chains a second command must be
rejected before it reaches the gate's confirm step, whatever separator is
used. Covers the `;` case reported by the professor and the newline case,
which the validator used to let through."""

from __future__ import annotations

import pytest

from src.core.confirmation_gate import ConfirmationGate
from src.validation.common import parse_command_line


CHAINED = [
    "nmap -sV 10.0.0.1; ls",
    "nmap -sV 10.0.0.1 ;ls",
    "nmap -sV 10.0.0.1 && whoami",
    "nmap -sV 10.0.0.1 || id",
    "nmap -sV 10.0.0.1 | sh",
    "nmap -sV 10.0.0.1 `id`",
    "nmap -sV 10.0.0.1 $(id)",
    "nmap -sV 10.0.0.1 > /tmp/x",
    "nmap -sV 10.0.0.1\nls",
    "nmap -sV 10.0.0.1\rls",
    "nmap -sV 10.0.0.1\x00ls",
    "nmap -sV 10.0.0.1\x1b[A",
]


@pytest.mark.parametrize("command", CHAINED)
def test_chained_or_multiline_commands_are_rejected(command):
    ok, _err, argv = parse_command_line(command)
    assert ok is False
    assert argv == []


@pytest.mark.parametrize("command", [
    "nmap -sV 10.0.0.1",
    "nmap -sS -p 22,80 10.0.0.0/24",
    "hydra -L users.txt -P pass.txt ssh://10.0.0.5",
    "evil-winrm -i 10.0.0.5 -u admin -p 'Passw0rd!'",
    "nmap -p 80 --script http-enum 10.0.0.1",
])
def test_plain_single_commands_are_accepted(command):
    ok, err, argv = parse_command_line(command)
    assert ok, err
    assert argv


def test_gate_refuses_newline_before_any_preview():
    gate = ConfirmationGate(channel="direct")
    result = gate.request("nmap -sV 10.0.0.1\nls", "10.0.0.1", skip_scope=True)
    assert result.ok is False
    assert result.preview_box is None
