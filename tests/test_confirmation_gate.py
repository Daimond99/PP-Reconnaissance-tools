"""Tests for src/core/confirmation_gate.py — the single human-in-the-loop
gate every Direct Tool Mode Execute passes through.

Covers: rejection of unsafe commands, scope enforcement, the exact-"yes"
confirmation contract, single-use replay protection (a confirmed gate must
not re-fire), secret masking via argv_override, and audit logging.
"""

from __future__ import annotations

from src.core.confirmation_gate import ConfirmationGate

IN_SCOPE = "192.168.1.10"       # inside default AUTHORIZED_SCOPE 192.168.1.0/24
OUT_SCOPE = "10.0.0.5"


def _gate():
    return ConfirmationGate(channel="test")


# --------------------------------------------------------------------------
# request() — validation + preview, never executes
# --------------------------------------------------------------------------

class TestRequest:
    def test_valid_command_builds_preview_and_argv(self):
        gate = _gate()
        res = gate.request("nmap -sV 192.168.1.10", IN_SCOPE, skip_scope=True)
        assert res.ok is True
        assert res.preview_box and "COMMAND PREVIEW" in res.preview_box
        assert res.argv == ["nmap", "-sV", "192.168.1.10"]

    def test_disallowed_command_rejected(self):
        gate = _gate()
        res = gate.request("rm -rf /", IN_SCOPE, skip_scope=True)
        assert res.ok is False
        assert "Rejected" in res.message

    def test_injection_rejected(self):
        gate = _gate()
        res = gate.request("nmap 192.168.1.10; rm -rf /", IN_SCOPE, skip_scope=True)
        assert res.ok is False

    def test_out_of_scope_rejected_when_scope_enforced(self):
        gate = _gate()
        res = gate.request("nmap -sV 10.0.0.5", OUT_SCOPE, skip_scope=False)
        assert res.ok is False
        assert "Scope violation" in res.message

    def test_in_scope_passes_when_scope_enforced(self):
        gate = _gate()
        res = gate.request("nmap -sV 192.168.1.10", IN_SCOPE, skip_scope=False)
        assert res.ok is True

    def test_skip_scope_bypasses_scope_check(self):
        gate = _gate()
        # out-of-scope target, but skip_scope=True (Direct Tool Mode's own lab)
        res = gate.request("nmap -sV 10.0.0.5", OUT_SCOPE, skip_scope=True)
        assert res.ok is True

    def test_request_does_not_execute(self):
        # request only prepares; argv is set but there's no side effect to run.
        gate = _gate()
        gate.request("nmap -sV 192.168.1.10", IN_SCOPE, skip_scope=True)
        assert gate._pending is True


# --------------------------------------------------------------------------
# confirm() — exact "yes" contract + single-use replay protection
# --------------------------------------------------------------------------

class TestConfirm:
    def test_exact_yes_confirms(self, audit):
        gate = _gate()
        gate.request("nmap -sV 192.168.1.10", IN_SCOPE, skip_scope=True)
        assert gate.confirm("yes") is True
        assert audit[-1]["executed"] is True

    def test_non_yes_cancels_and_clears_pending(self, audit):
        gate = _gate()
        gate.request("nmap -sV 192.168.1.10", IN_SCOPE, skip_scope=True)
        assert gate.confirm("no") is False
        assert gate._pending is False
        assert audit[-1]["executed"] is False

    def test_confirm_without_request_is_false(self):
        gate = _gate()
        assert gate.confirm("yes") is False

    def test_single_use_no_double_execute(self, audit):
        # The replay-protection fix: a confirmed gate must not re-fire on a
        # second confirm("yes"), which would re-run and re-log the argv.
        gate = _gate()
        gate.request("nmap -sV 192.168.1.10", IN_SCOPE, skip_scope=True)
        assert gate.confirm("yes") is True
        assert gate.confirm("yes") is False
        # exactly one executed=True audit entry
        assert sum(1 for c in audit if c["executed"]) == 1


# --------------------------------------------------------------------------
# argv_override — secret masking
# --------------------------------------------------------------------------

class TestSecretMasking:
    def test_masked_command_logged_real_argv_executed(self, audit):
        gate = _gate()
        real = ["hydra", "-l", "admin", "-p", "S3cret!", "192.168.1.10", "ssh"]
        masked = "hydra -l admin -p ***** 192.168.1.10 ssh"
        res = gate.request(masked, IN_SCOPE, argv_override=real, skip_scope=True)
        assert res.ok is True
        # what runs is the real argv...
        assert gate.argv == real
        # ...but what's stored/previewed/logged is the masked string
        assert gate.command == masked
        assert "S3cret!" not in gate.command
        gate.confirm("yes")
        assert "S3cret!" not in audit[-1]["command"]


# --------------------------------------------------------------------------
# cancel() — logs a non-executed decision
# --------------------------------------------------------------------------

class TestCancel:
    def test_cancel_logs_not_executed(self, audit):
        gate = _gate()
        gate.request("nmap -sV 192.168.1.10", IN_SCOPE, skip_scope=True)
        gate.cancel("user_declined")
        assert audit[-1]["executed"] is False
        assert audit[-1]["response"] == "user_declined"
        assert gate._pending is False
