"""Resuming a stopped or interrupted scan from the history: only resumable runs
offer Resume, the same run record continues, and the driver is started with
the checkpoint instead of a new target."""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from src.core import scan_history
from src.core.scan_history import FINISHED, INTERRUPTED, RUNNING, STOPPED, ScanHistory


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def chain_dir(tmp_path, monkeypatch):
    from src.ui import wizard_runner
    root = tmp_path / "chain_wizard"
    monkeypatch.setattr(wizard_runner, "_chain_dir", lambda: root)
    return root


@pytest.fixture
def history(chain_dir, monkeypatch):
    root = chain_dir / "results" / "history"
    monkeypatch.setattr(scan_history, "DEFAULT_ROOT", root)
    return ScanHistory(root)


def _checkpoint(history, run, finished=False):
    history.checkpoint_path(run.id).parent.mkdir(parents=True, exist_ok=True)
    history.checkpoint_path(run.id).write_text(
        json.dumps({"target": run.target, "finished": finished}), encoding="utf-8")


class TestResumable:
    def test_interrupted_run_with_unfinished_checkpoint_is_resumable(self, history):
        run = history.start("10.0.0.5")
        history.add_row(run, ("Scan", "22/tcp", "-", "ssh", "Open"))
        history.finish(run, STOPPED)
        _checkpoint(history, run)
        assert history.resumable(history.load(run.id))

    def test_finished_chain_is_not_resumable(self, history):
        run = history.start("10.0.0.5")
        history.finish(run, FINISHED, 0)
        _checkpoint(history, run, finished=True)
        assert not history.resumable(history.load(run.id))

    def test_run_without_checkpoint_is_not_resumable(self, history):
        run = history.start("10.0.0.5")
        history.finish(run, STOPPED)
        assert not history.resumable(history.load(run.id))

    def test_running_run_is_not_resumable(self, history):
        run = history.start("10.0.0.5")
        _checkpoint(history, run)
        assert not history.resumable(history.load(run.id))

    def test_checkpoint_files_are_not_listed_as_runs(self, history):
        run = history.start("10.0.0.5")
        _checkpoint(history, run)
        assert [r.id for r in history.runs()] == [run.id]

    def test_reopen_sets_the_run_running_again(self, history):
        run = history.start("10.0.0.5")
        history.finish(run, STOPPED)
        history.reopen(history.load(run.id))
        assert history.load(run.id).status == RUNNING


class _FakeDriver(QObject):
    menuRequested = Signal(dict)
    textRequested = Signal(dict)
    multiselectRequested = Signal(dict)
    confirmRequested = Signal(dict)
    sudoPasswordRequested = Signal()
    statusUpdate = Signal(dict)
    rawOutput = Signal(str)
    finished = Signal(int)
    errorOccurred = Signal(str)

    created: list = []

    def __init__(self, target, user_wordlist, pass_wordlist, parent=None,
                 checkpoint=None, resume=None):
        super().__init__(parent)
        self.args = dict(target=target, checkpoint=checkpoint, resume=resume)
        _FakeDriver.created.append(self)

    def start(self):
        pass

    def stop(self):
        pass


class TestRunnerResume:
    def test_resume_continues_the_same_run_with_the_checkpoint(self, app, history, chain_dir, monkeypatch):
        from src.ui import wizard_runner
        _FakeDriver.created.clear()
        monkeypatch.setattr(wizard_runner, "WizardDriver", _FakeDriver)
        runner = wizard_runner.WizardRunner()
        runner._history = history
        run = history.start("10.0.0.5")
        history.add_row(run, ("Scan", "22/tcp", "-", "ssh", "Open"))
        history.finish(run, STOPPED)
        _checkpoint(history, run)

        runner.resume(run.id)

        assert len(_FakeDriver.created) == 1
        args = _FakeDriver.created[0].args
        assert args["resume"] == args["checkpoint"]
        assert args["resume"].endswith(f"{run.id}.checkpoint.json")
        assert runner.progress._table.rowCount() >= 1
        assert history.load(run.id).status == RUNNING
        runner.close()

    def test_resume_refuses_a_finished_run(self, app, history, monkeypatch):
        from src.ui import wizard_runner
        from PySide6.QtWidgets import QMessageBox
        _FakeDriver.created.clear()
        monkeypatch.setattr(wizard_runner, "WizardDriver", _FakeDriver)
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
        runner = wizard_runner.WizardRunner()
        runner._history = history
        run = history.start("10.0.0.5")
        history.finish(run, FINISHED, 0)
        runner.resume(run.id)
        assert _FakeDriver.created == []
        assert history.load(run.id).status == FINISHED
        runner.close()


class TestHistoryDialogResume:
    def test_resume_button_follows_the_selected_run(self, app, history):
        from src.ui.wizard_runner import _HistoryDialog
        stopped = history.start("10.0.0.5")
        history.finish(stopped, STOPPED)
        _checkpoint(history, stopped)
        done = history.start("10.0.0.6")
        history.finish(done, FINISHED, 0)
        dialog = _HistoryDialog(history)
        resumable_rows = [i for i, run in enumerate(dialog._runs) if history.resumable(run)]
        assert len(resumable_rows) == 1
        dialog._table.setCurrentCell(resumable_rows[0], 0)
        assert dialog._resume_btn.isEnabled()
        other = [i for i in range(len(dialog._runs)) if i not in resumable_rows][0]
        dialog._table.setCurrentCell(other, 0)
        assert not dialog._resume_btn.isEnabled()
        dialog.close()
