"""Headless functional smoke test for the GUI — builds the real window and
drives the widget code paths (navigation, top-bar warhead repopulation,
dropdown, results rendering, input queue) without a human clicking.

Runs under Qt's `offscreen` platform so it needs no display. This is the
regression net for the `src/ui/widgets/` package split — it catches breakage
that import-only checks and the validator/gate unit tests can't.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets")  # window needs QtWebEngine

from PySide6.QtWidgets import QApplication

from src.ui.widgets import (
    TopBar, DropdownButton, ResultsDisplayTab, InputManagementTab, MainContentArea,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from src.ui.main_window import ReconMainWindow
    return ReconMainWindow()


def _find_topbar(win) -> TopBar:
    for attr in vars(win).values():
        if isinstance(attr, TopBar):
            return attr
    raise AssertionError("no TopBar on the window")


class TestWindowStructure:
    def test_five_pages_correct_types(self, window):
        ma = window.main_area
        assert isinstance(ma, MainContentArea)
        assert ma.stack.count() == 5
        assert isinstance(ma.results_tab, ResultsDisplayTab)
        assert isinstance(ma.input_tab, InputManagementTab)
        assert hasattr(ma, "wizard_tab") and hasattr(ma, "raw_output_tab")

    def test_sidebar_navigates_all_pages(self, window):
        hits: list[int] = []
        window.sidebar.navigate.connect(hits.append)
        for i in range(5):
            window.sidebar.select_index(i)
        assert hits == [0, 1, 2, 3, 4]


class TestTopBar:
    def test_warheads_repopulate_per_tool(self, window):
        tb = _find_topbar(window)
        tb.set_warhead_profiles("Nmap")
        assert len(tb.warhead_combo._items) > 0
        tb.set_warhead_profiles("Hydra")
        assert len(tb.warhead_combo._items) > 0

    def test_default_target(self, window):
        assert _find_topbar(window).target_text() == "192.168.1.0/24"


class TestDropdownButton:
    def test_select_and_clear(self):
        dd = DropdownButton(["a", "b", "c"])
        got: list[str] = []
        dd.currentTextChanged.connect(got.append)
        assert dd.currentText() == "a"
        dd._select("b")
        assert dd.currentText() == "b" and got == ["b"]
        dd.clear()
        assert dd.currentText() == "" and dd._items == []


class TestResultsDisplay:
    def test_scan_and_credential_rows_render(self, window):
        rt = window.main_area.results_tab
        host = {"host": "10.0.0.1", "state": "up", "open": 1, "filtered": 0,
                "closed": 0, "scanned": 1, "uptime": "-", "lastboot": "-",
                "ip": "10.0.0.1", "hostname": "h", "os": "Linux", "accuracy": 90,
                "ports": [{"port": 22, "proto": "tcp", "service": "ssh",
                           "state": "open"}]}
        rt.add_scan_results([host])
        assert rt.host_list.count() == 1
        rt.add_credential_results("hydra", "10.0.0.1",
                                  [{"host": "10.0.0.1", "port": 22,
                                    "service": "ssh", "login": "admin",
                                    "password": "pw"}], "now")
        assert rt.host_list.count() == 2
        rt.host_list.setCurrentRow(0)   # host detail view
        rt.host_list.setCurrentRow(1)   # credentials detail view


class TestInputQueue:
    def test_add_status_and_xml_roundtrip(self, window):
        it = window.main_area.input_tab
        row = it.add_entry("nmap -sV 10.0.0.1", status="Running")
        it.set_status(row, "Done")
        assert it.table.rowCount() == 1
        xml = InputManagementTab.build_scan_xml("nmap -sV 10.0.0.1")
        assert "nmap -sV 10.0.0.1" in xml
