"""Regression tests for the Wizard Console fixes: the multiselect dialog keeps
hand-picked rows when "Add recommended" is pressed, the run-log viewer reads
the log the CLI reports, and closing/reopening state is tracked per run.

Runs headless under Qt's `offscreen` platform, like test_gui_smoke.py.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _list_for(items: list[dict], checked: set[int], app) -> QListWidget:
    lst = QListWidget()
    for i, _item in enumerate(items):
        li = QListWidgetItem(f"row {i + 1}")
        li.setFlags(li.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        li.setCheckState(Qt.CheckState.Checked if i in checked else Qt.CheckState.Unchecked)
        lst.addItem(li)
    return lst


def _checked(lst: QListWidget) -> set[int]:
    return {i for i in range(lst.count())
            if lst.item(i).checkState() == Qt.CheckState.Checked}


class TestAddRecommended:
    ITEMS = [
        {"priority": 2}, {"priority": 4}, {"priority": 3}, {"priority": 4},
    ]

    def test_adds_recommended_and_keeps_hand_picks(self, app):
        from src.ui.wizard_dialogs import _check_matching
        lst = _list_for(self.ITEMS, {0}, app)  # user had row 1 picked
        _check_matching(lst, self.ITEMS, "priority", 4)
        assert _checked(lst) == {0, 1, 3}

    def test_does_not_uncheck_non_recommended_rows(self, app):
        from src.ui.wizard_dialogs import _check_matching
        lst = _list_for(self.ITEMS, {2}, app)  # optional row picked
        _check_matching(lst, self.ITEMS, "priority", 4)
        assert _checked(lst) == {1, 2, 3}

    def test_counts_checked_rows(self, app):
        from src.ui.wizard_dialogs import _checked_count
        lst = _list_for(self.ITEMS, {0, 3}, app)
        assert _checked_count(lst) == 2


class TestRunLog:
    def test_logfile_status_sets_current_log(self, app):
        from src.ui.wizard_runner import WizardRunner, _chain_dir
        runner = WizardRunner()
        assert runner.current_log_path() is None
        runner._on_status({"type": "status", "kind": "logfile",
                           "text": "results/logs/chain_x.log",
                           "data": {"path": "results/logs/chain_x.log"}})
        assert runner.current_log_path() == _chain_dir() / "results/logs/chain_x.log"
        assert runner.is_running() is False
        runner.close()


@pytest.mark.skipif(os.name != "nt", reason="opens a Windows console window")
def test_shell_request_opens_console_with_tty(app, monkeypatch):
    from src.ui import wizard_runner
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: calls.append((argv, kw)))
    runner = wizard_runner.WizardRunner()
    runner._on_status({"type": "status", "kind": "shell_request",
                       "text": "evil-winrm", "data": {"cmd": "evil-winrm -i 10.0.0.5 -u a -p b",
                                                      "title": "evil-winrm"}})
    argv, kw = calls[0]
    assert argv[:3] == ["wsl.exe", "-e", "bash"]
    assert "docker exec -it" in argv[-1] and "evil-winrm -i 10.0.0.5" in argv[-1]
    assert kw["creationflags"] == subprocess.CREATE_NEW_CONSOLE
    runner.close()
