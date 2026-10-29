"""run_chain with a checkpoint: a run cut short can be resumed without
scanning again and without running a step twice, and each step still asks."""

from __future__ import annotations

import pytest

from core import ui_driver
from core.checkpoint import Checkpoint
from core.models import ScanResult
from wizard import chain


class _StopAfter(Exception):
    pass


class _FakeUI(ui_driver.UI):
    def __init__(self, stop_after: int | None = None):
        self.stop_after = stop_after
        self.confirms = 0

    def menu(self, title, options, default=""):
        return default

    def text(self, prompt, default=""):
        return default

    def multiselect(self, title, items):
        return "a"

    def confirm(self, cmd, impact, title="Confirm"):
        self.confirms += 1
        if self.stop_after is not None and self.confirms > self.stop_after:
            raise _StopAfter()
        return True

    def status(self, kind, text, data=None):
        pass


@pytest.fixture
def world(monkeypatch, tmp_path):
    calls: list[str] = []
    scans: list[str] = []

    def fake_scan(target):
        scans.append(target)
        return [ScanResult(port=22, service="ssh"), ScanResult(port=445, service="microsoft-ds")]

    def fake_run(cmd, logfile=None, timeout=600):
        calls.append(cmd)
        return "", 0

    monkeypatch.setattr(chain, "scan_target", fake_scan)
    monkeypatch.setattr(chain, "run_cmd", fake_run)
    previous = ui_driver.get_ui()
    yield calls, scans, tmp_path
    ui_driver.set_ui(previous)


def _run(ui, checkpoint, resume=None):
    ui_driver.set_ui(ui)
    chain.run_chain("10.0.0.5", "", "", checkpoint_path=checkpoint, resume=resume)


def test_fresh_run_writes_scan_selection_outcomes_and_finish(world):
    calls, scans, tmp = world
    path = tmp / "run.checkpoint.json"
    _run(_FakeUI(), str(path))
    state = Checkpoint.load(path)
    assert state.finished is True
    assert state.scan == [{"port": 22, "service": "ssh"}, {"port": 445, "service": "microsoft-ds"}]
    assert state.selected and set(state.outcomes) == set(state.selected)
    assert len(calls) == len(state.selected)


def test_resume_does_not_scan_again_or_repeat_finished_steps(world):
    calls, scans, tmp = world
    path = tmp / "run.checkpoint.json"
    with pytest.raises(_StopAfter):
        _run(_FakeUI(stop_after=1), str(path))
    partial = Checkpoint.load(path)
    assert partial.finished is False
    done_before = len(partial.outcomes)
    assert done_before == 1
    calls.clear()
    scans.clear()

    _run(_FakeUI(), str(path), resume=partial)

    assert scans == []
    assert len(calls) == len(partial.selected) - done_before
    assert Checkpoint.load(path).finished is True


def test_resume_keeps_the_original_selection_and_logfile(world):
    calls, scans, tmp = world
    path = tmp / "run.checkpoint.json"
    with pytest.raises(_StopAfter):
        _run(_FakeUI(stop_after=1), str(path))
    partial = Checkpoint.load(path)
    _run(_FakeUI(), str(path), resume=partial)
    final = Checkpoint.load(path)
    assert final.selected == partial.selected
    assert final.logfile == partial.logfile


def test_checkpoint_round_trips_through_json(tmp_path):
    state = Checkpoint(target="10.0.0.5", user_wordlist="/a.txt", pass_wordlist="/b.txt",
                       logfile="results/logs/chain_x.log", scan=[{"port": 22, "service": "ssh"}],
                       selected=["22|ssh|Hydra|x"], outcomes={"22|ssh|Hydra|x": "done"})
    path = tmp_path / "c.json"
    state.save(path)
    assert Checkpoint.load(path) == state
