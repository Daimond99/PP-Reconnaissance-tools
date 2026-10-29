"""Settings ▸ View Wizard Log… must open the log viewer for the chain_wizard
logs. It used to read a class attribute that did not exist, so the slot raised
and nothing appeared on screen."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication

pytest.importorskip("PySide6.QtWebEngineWidgets")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_view_wizard_log_opens_the_viewer(app, monkeypatch):
    from src.ui import main_window as mw
    opened = []

    class _FakeViewer:
        def __init__(self, paths, selected=None, parent=None):
            opened.append(list(paths))

        def exec(self):
            return 0

    monkeypatch.setattr(mw, "LogViewerDialog", _FakeViewer)
    window = mw.ReconMainWindow()
    window._on_view_wizard_log()
    assert len(opened) == 1
