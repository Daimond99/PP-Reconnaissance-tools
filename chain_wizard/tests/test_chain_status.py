"""chain.run_chain must emit structured `get_ui().status(...)` events for
every scan result, step outcome, and harvested credential, plus a final
summary — these feed the GUI's `WizardProgressView` (src/ui/wizard_runner.py)
in place of a printed console log."""

from __future__ import annotations

from unittest.mock import patch

from core.models import AttackPlan, ScanResult, Step
from core.ui_driver import UI
from wizard import chain


class RecordingUI(UI):
    """No-op stand-in for CliUI/IpcUI that just records every status()
    call — confirm() always accepts so _execute_step actually runs."""

    def __init__(self):
        self.statuses: list[tuple[str, str, dict]] = []

    def confirm(self, cmd, impact, title="Confirm"):
        return True

    def status(self, kind, text, data=None):
        self.statuses.append((kind, text, data or {}))

    def multiselect(self, title, items):
        return "a"  # select all


def _kinds(ui: RecordingUI) -> list[str]:
    return [k for k, _, _ in ui.statuses]


def test_run_chain_emits_scan_result_per_open_port():
    ui = RecordingUI()
    scan_results = [ScanResult(port=22, service="ssh"), ScanResult(port=80, service="http")]
    with patch.object(chain, "get_ui", return_value=ui), \
         patch("wizard.chain.scan_target", return_value=scan_results), \
         patch("wizard.chain.build_plan", return_value=AttackPlan(
             target="10.0.0.1", user_wordlist="", pass_wordlist="", steps=[])):
        chain.run_chain("10.0.0.1", "", "", "auto")

    scan_events = [(t, d) for k, t, d in ui.statuses if k == "scan_result"]
    assert scan_events == [
        ("22/tcp → ssh", {"port": 22, "service": "ssh"}),
        ("80/tcp → http", {"port": 80, "service": "http"}),
    ]


def test_run_chain_emits_step_done_and_summary():
    ui = RecordingUI()
    step = Step(name="SSH brute force", tool="hydra",
                command_template="hydra -l root {target}", impact="brute force")
    plan = AttackPlan(target="10.0.0.1", user_wordlist="u.txt", pass_wordlist="p.txt",
                       steps=[(22, "ssh", step)])
    with patch.object(chain, "get_ui", return_value=ui), \
         patch("wizard.chain.scan_target", return_value=[ScanResult(port=22, service="ssh")]), \
         patch("wizard.chain.build_plan", return_value=plan), \
         patch("wizard.chain.run_cmd", return_value=("no creds here", "")):
        chain.run_chain("10.0.0.1", "u.txt", "p.txt", "semi")

    assert "step_start" in _kinds(ui)
    start_event = next(d for k, _, d in ui.statuses if k == "step_start")
    assert start_event == {"port": 22, "service": "ssh", "tool": "hydra",
                            "name": "SSH brute force"}
    assert "step_done" in _kinds(ui)
    step_event = next(d for k, _, d in ui.statuses if k == "step_done")
    assert step_event == {"port": 22, "service": "ssh", "tool": "hydra",
                           "name": "SSH brute force", "outcome": "done"}
    assert "summary" in _kinds(ui)
    summary = next(d for k, _, d in ui.statuses if k == "summary")
    assert summary["executed"] == 1
    assert summary["skipped"] == 0


def test_run_chain_emits_cred_found_for_each_harvested_credential():
    ui = RecordingUI()
    step = Step(name="SSH brute force", tool="hydra",
                command_template="hydra -l root {target}", impact="brute force")
    plan = AttackPlan(target="10.0.0.1", user_wordlist="u.txt", pass_wordlist="p.txt",
                       steps=[(22, "ssh", step)])
    hydra_output = "[22][ssh] host: 10.0.0.1   login: admin   password: hunter2"
    with patch.object(chain, "get_ui", return_value=ui), \
         patch("wizard.chain.scan_target", return_value=[ScanResult(port=22, service="ssh")]), \
         patch("wizard.chain.build_plan", return_value=plan), \
         patch("wizard.chain.run_cmd", return_value=(hydra_output, "")), \
         patch("wizard.chain._save_loot", return_value="loot.txt"), \
         patch("wizard.chain._offer_post_exploit"):
        chain.run_chain("10.0.0.1", "u.txt", "p.txt", "semi")

    cred_events = [(t, d) for k, t, d in ui.statuses if k == "cred_found"]
    assert cred_events == [
        ("admin:hunter2 on 22/ssh",
         {"port": 22, "service": "ssh", "user": "admin", "password": "hunter2"}),
    ]
