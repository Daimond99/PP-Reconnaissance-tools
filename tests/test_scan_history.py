"""Scan history: runs are written as they happen, survive a closed window,
can be reloaded without running anything again, and the progress/results
tables can be searched and filtered."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication

from src.core import scan_history
from src.core.scan_history import (
    FINISHED, FAILED, INTERRUPTED, RUNNING, STOPPED, ScanHistory,
)


@pytest.fixture
def history(tmp_path):
    return ScanHistory(tmp_path / "history")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestScanHistoryStore:
    def test_run_is_on_disk_before_it_finishes(self, history):
        run = history.start("10.0.0.5")
        history.add_row(run, ("Scan", "22/tcp", "-", "ssh", "Open"))
        reloaded = history.load(run.id)
        assert reloaded.status == RUNNING
        assert reloaded.rows == [["Scan", "22/tcp", "-", "ssh", "Open"]]

    def test_finish_records_status_and_exit_code(self, history):
        run = history.start("10.0.0.5")
        history.finish(run, FINISHED, 0)
        reloaded = history.load(run.id)
        assert reloaded.status == FINISHED
        assert reloaded.exit_code == 0

    def test_first_finish_wins(self, history):
        run = history.start("10.0.0.5")
        history.finish(run, STOPPED)
        history.finish(run, FINISHED, 0)
        assert history.load(run.id).status == STOPPED

    def test_running_runs_become_interrupted_on_recovery(self, history):
        live = history.start("10.0.0.5")
        done = history.start("10.0.0.6")
        history.finish(done, FINISHED, 0)
        assert history.mark_interrupted() == 1
        assert history.load(live.id).status == INTERRUPTED
        assert history.load(done.id).status == FINISHED

    def test_runs_are_listed_newest_first(self, history):
        first = history.start("10.0.0.1")
        second = history.start("10.0.0.2")
        first.started = "2026-10-28 09:00:00"
        second.started = "2026-10-28 10:00:00"
        history._save(first)
        history._save(second)
        assert [run.target for run in history.runs()] == ["10.0.0.2", "10.0.0.1"]

    def test_missing_run_loads_as_none(self, history):
        assert history.load("does-not-exist") is None

    def test_log_path_is_kept(self, history):
        run = history.start("10.0.0.5")
        history.set_log_path(run, "results/logs/chain_x.log")
        assert history.load(run.id).log_path == "results/logs/chain_x.log"

    def test_failed_status_is_stored(self, history):
        run = history.start("10.0.0.5")
        history.finish(run, FAILED)
        assert history.load(run.id).status == FAILED


class TestProgressFilter:
    ROWS = [
        ("Scan", "22/tcp", "-", "ssh", "Open"),
        ("Scan", "80/tcp", "-", "http", "Open"),
        ("Step", "22/ssh", "hydra", "SSH brute", "Done"),
        ("Credential", "22/ssh", "-", "admin:pw", "Found"),
    ]

    def _view(self, app):
        from src.ui.wizard_runner import WizardProgressView
        return WizardProgressView()

    def test_type_filter_limits_rows(self, app):
        view = self._view(app)
        for row in self.ROWS:
            view.add_row(row)
        view._type.setCurrentText("Credential")
        assert view._table.rowCount() == 1
        assert view._table.item(0, 4).text() == "Found"

    def test_search_matches_any_column_case_insensitively(self, app):
        view = self._view(app)
        for row in self.ROWS:
            view.add_row(row)
        view._search.setText("HYDRA")
        assert view._table.rowCount() == 1
        view._search.setText("ssh")
        assert view._table.rowCount() == 3

    def test_clear_restores_all_rows(self, app):
        view = self._view(app)
        for row in self.ROWS:
            view.add_row(row)
        view._search.setText("nothing matches this")
        assert view._table.rowCount() == 0
        view._search.clear()
        assert view._table.rowCount() == 4

    def test_show_saved_replaces_rows_and_shows_banner(self, app):
        view = self._view(app)
        view.add_row(("Info", "-", "-", "live row", "-"))
        view.show_saved([list(row) for row in self.ROWS], "Saved run · 10.0.0.5")
        assert view._table.rowCount() == 4
        assert view._banner.text() == "Saved run · 10.0.0.5"


class TestRunnerRecordsRuns:
    def test_status_rows_and_log_path_are_recorded(self, app, tmp_path, monkeypatch):
        monkeypatch.setattr(scan_history, "DEFAULT_ROOT", tmp_path / "history")
        from src.ui.wizard_runner import WizardRunner
        runner = WizardRunner()
        runner._run = runner.history().start("10.0.0.5")
        runner._on_status({"type": "status", "kind": "scan_result", "text": "22/tcp",
                           "data": {"port": 22, "service": "ssh"}})
        runner._on_status({"type": "status", "kind": "logfile", "text": "results/logs/chain_x.log",
                           "data": {"path": "results/logs/chain_x.log"}})
        stored = runner.history().load(runner._run.id)
        assert stored.rows[0] == ["Scan", "22/tcp", "-", "ssh", "Open"]
        assert stored.log_path == "results/logs/chain_x.log"
        runner.close()

    def test_stop_marks_the_run_stopped(self, app, tmp_path, monkeypatch):
        monkeypatch.setattr(scan_history, "DEFAULT_ROOT", tmp_path / "history")
        from src.ui.wizard_runner import WizardRunner

        class _StubDriver:
            def stop(self):
                pass

        runner = WizardRunner()
        runner._run = runner.history().start("10.0.0.5")
        runner._driver = _StubDriver()
        run_id = runner._run.id
        runner.stop()
        assert runner.history().load(run_id).status == STOPPED
        runner._driver = None
        runner.close()


class TestResultsFilter:
    def _tab(self, app):
        from src.ui.widgets.results_display import ResultsDisplayTab
        return ResultsDisplayTab()

    def _host(self, ip):
        return {"host": ip, "label": f"{ip} · scan", "state": "up", "open": 0,
                "filtered": 0, "closed": 0, "scanned": 1, "uptime": "-",
                "lastboot": "-", "ip": ip, "hostname": "-", "os": "-",
                "accuracy": 0, "ports": []}

    def test_kind_filter_separates_scans_and_credentials(self, app):
        tab = self._tab(app)
        tab.add_scan_results([self._host("10.0.0.1"), self._host("10.0.0.2")])
        tab.add_credential_results("hydra", "10.0.0.1",
                                   [{"host": "10.0.0.1", "port": 22, "service": "ssh",
                                     "login": "a", "password": "b"}], "now")
        assert tab.host_list.count() == 3
        tab._kind.setCurrentText("Credentials")
        assert tab.host_list.count() == 1
        tab._kind.setCurrentText("Scan results")
        assert tab.host_list.count() == 2

    def test_search_narrows_host_list(self, app):
        tab = self._tab(app)
        tab.add_scan_results([self._host("10.0.0.1"), self._host("192.168.1.9")])
        tab._search.setText("192.168")
        assert tab.host_list.count() == 1
        tab._search.setText("nothing")
        assert tab.host_list.count() == 0
        tab._search.clear()
        assert tab.host_list.count() == 2
