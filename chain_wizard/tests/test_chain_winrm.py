"""evil-winrm is an interactive shell. After a WinRM credential is harvested the
chain must hand it to `UI.open_shell` (a real TTY), never to `run_cmd`, which
captures stdout with no TTY and so never produced a session."""

from __future__ import annotations

import pytest

from core import ui_driver
from core.models import AttackPlan
from wizard import chain


class _FakeUI(ui_driver.UI):
    def __init__(self, confirm_reply: bool):
        self.confirm_reply = confirm_reply
        self.shells: list[tuple[str, str]] = []

    def confirm(self, cmd, impact, title="Confirm"):
        self.last_confirm = cmd
        return self.confirm_reply

    def open_shell(self, cmd, title="Interactive session"):
        self.shells.append((cmd, title))

    def status(self, kind, text, data=None):
        pass


@pytest.fixture
def fake_ui():
    previous = ui_driver.get_ui()
    ui = _FakeUI(confirm_reply=True)
    ui_driver.set_ui(ui)
    yield ui
    ui_driver.set_ui(previous)


@pytest.fixture
def no_captured_run(monkeypatch):
    calls = []
    monkeypatch.setattr(chain, "run_cmd", lambda *a, **kw: calls.append(a) or ("", 0))
    return calls


def test_confirmed_winrm_opens_shell_not_captured_run(fake_ui, no_captured_run):
    plan = AttackPlan(target="10.0.0.5", user_wordlist="", pass_wordlist="")
    chain._offer_winrm(plan, 5985, ("admin", "P@ss w0rd"))
    assert no_captured_run == []
    assert len(fake_ui.shells) == 1
    cmd, _title = fake_ui.shells[0]
    assert cmd.startswith("evil-winrm -i 10.0.0.5 -u admin ")
    assert "'P@ss w0rd'" in cmd  # shell-quoted, same as the confirmed preview


def test_winrm_over_tls_adds_flag(fake_ui, no_captured_run):
    plan = AttackPlan(target="10.0.0.5", user_wordlist="", pass_wordlist="")
    chain._offer_winrm(plan, 5986, ("admin", "pw"))
    assert fake_ui.shells[0][0].endswith(" -S")


def test_declined_winrm_opens_nothing(fake_ui, no_captured_run):
    fake_ui.confirm_reply = False
    plan = AttackPlan(target="10.0.0.5", user_wordlist="", pass_wordlist="")
    chain._offer_winrm(plan, 5985, ("admin", "pw"))
    assert fake_ui.shells == []
    assert no_captured_run == []


def test_default_logfile_lives_under_results_logs():
    plan = AttackPlan(target="10.0.0.5", user_wordlist="", pass_wordlist="")
    assert plan.logfile.startswith("results/logs/chain_")
    assert plan.logfile.endswith(".log")
