"""Shutdown path: every terminal, the wizard process, and the preflight thread
are released before the process exits, so no Qt thread or process is
destroyed while still running (that is a fatal abort in Qt)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication, QMessageBox

pytest.importorskip("PySide6.QtWebEngineWidgets")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_release_background_work_is_safe_to_call_twice(app):
    from src.ui.main_window import ReconMainWindow
    window = ReconMainWindow()
    window.release_background_work()
    window.release_background_work()


def test_close_with_confirmation_releases_everything(app, monkeypatch):
    from src.ui.main_window import ReconMainWindow
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    window = ReconMainWindow()
    calls = []
    original = window.release_background_work
    monkeypatch.setattr(window, "release_background_work", lambda: (calls.append(1), original()))
    window.close()
    assert calls == [1]


def test_wizard_driver_stop_without_a_process_is_a_no_op(app):
    from src.core.wizard_driver import WizardDriver
    driver = WizardDriver(target="10.0.0.5", user_wordlist="", pass_wordlist="")
    driver.stop()


def test_raw_output_stop_before_any_terminal_exists(app):
    from src.ui.widgets.raw_output import RawOutputTab
    tab = RawOutputTab()
    tab.stop()
