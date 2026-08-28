"""Tests for chain_wizard/core/ui_driver.py — the JSON IPC protocol IpcUI
speaks with the Qt GUI driver (src/core/wizard_driver.py), and that CliUI's
reply-parsing (default fallback, etc.) still behaves like the original
input()-based prompts."""

from __future__ import annotations

import io
import json

from core.ui_driver import CliUI, IpcUI, get_ui, set_ui


def _ipc(replies: list[dict]) -> tuple[IpcUI, io.StringIO]:
    stdin = io.StringIO("".join(json.dumps(r) + "\n" for r in replies))
    stdout = io.StringIO()
    return IpcUI(stdin=stdin, stdout=stdout), stdout


def _sent(stdout: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stdout.getvalue().splitlines() if line]


class TestIpcUiMenu:
    def test_sends_request_and_returns_reply(self):
        ui, out = _ipc([{"reply": "2"}])
        result = ui.menu("Pick one", ["1. a", "2. b"], default="1")
        assert result == "2"
        sent = _sent(out)
        assert sent == [{"type": "menu", "title": "Pick one",
                          "options": ["1. a", "2. b"], "default": "1"}]

    def test_falls_back_to_default_on_missing_reply_key(self):
        ui, _ = _ipc([{}])
        assert ui.menu("Pick one", ["1", "2"], default="1") == "1"


class TestIpcUiText:
    def test_returns_typed_reply(self):
        ui, out = _ipc([{"reply": "/tmp/wordlist.txt"}])
        assert ui.text("User wordlist", "/default.txt") == "/tmp/wordlist.txt"
        assert _sent(out)[0]["type"] == "text"

    def test_empty_line_returns_default(self):
        stdin = io.StringIO("")  # subprocess stdin closed
        stdout = io.StringIO()
        ui = IpcUI(stdin=stdin, stdout=stdout)
        assert ui.text("Target", "1.2.3.4") == "1.2.3.4"


class TestIpcUiMultiselect:
    def test_round_trips_raw_picks_string(self):
        items = [{"port": 22, "service": "ssh", "tool": "hydra",
                  "name": "SSH brute", "priority": 4}]
        ui, out = _ipc([{"reply": "1,2"}])
        assert ui.multiselect("Attack plan", items) == "1,2"
        sent = _sent(out)[0]
        assert sent["items"] == items


class TestIpcUiConfirm:
    def test_true_only_on_truthy_reply(self):
        ui, out = _ipc([{"reply": True}])
        assert ui.confirm("hydra -l admin ...", "Brute force attempt", title="Step") is True
        sent = _sent(out)[0]
        assert sent == {"type": "confirm", "title": "Step",
                         "cmd": "hydra -l admin ...", "impact": "Brute force attempt"}

    def test_false_on_falsy_or_missing_reply(self):
        ui, _ = _ipc([{"reply": False}])
        assert ui.confirm("cmd", "impact") is False
        ui2, _ = _ipc([{}])
        assert ui2.confirm("cmd", "impact") is False


class TestIpcUiSudoPassword:
    def test_requests_and_returns_password(self):
        ui, out = _ipc([{"reply": "hunter2"}])
        assert ui.sudo_password() == "hunter2"
        assert _sent(out)[0] == {"type": "sudo_password"}

    def test_needs_sudo_password_flag(self):
        assert IpcUI().needs_sudo_password is True
        assert CliUI().needs_sudo_password is False


class TestIpcUiStatus:
    def test_one_way_no_reply_expected(self):
        stdout = io.StringIO()
        ui = IpcUI(stdin=io.StringIO(""), stdout=stdout)
        ui.status("cred_found", "admin:hunter2 on 22/ssh", {"port": 22})
        sent = _sent(stdout)
        assert sent == [{"type": "status", "kind": "cred_found",
                          "text": "admin:hunter2 on 22/ssh", "data": {"port": 22}}]


class TestUiSingleton:
    def test_set_get_round_trip(self):
        original = get_ui()
        try:
            marker = CliUI()
            set_ui(marker)
            assert get_ui() is marker
        finally:
            set_ui(original)
