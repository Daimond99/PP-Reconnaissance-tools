import faulthandler
import os
import sys
from pathlib import Path

# QtWebEngine's Chromium GPU process can segfault on WSLg, headless Linux, or
# systems without a usable EGL/GL driver (Mesa/ZINK is a common failure mode).
# These must be configured before importing PySide6/QtWebEngine or creating the
# QApplication, otherwise Chromium may already have selected its GPU backend.
if sys.platform.startswith("linux"):
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --disable-gpu-compositing --no-sandbox --disable-software-rasterizer",
    )
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    # Keep Qt's own compositor out of EGL too; Chromium flags only govern
    # QtWebEngine's child processes, while the view's host is a Qt surface.
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from src import preflight
from src.config import STYLESHEET, WINDOW_TITLE, BG, TEXT
from src.ui.main_window import ReconMainWindow

# Native crashes (e.g. a Qt/QThread teardown race) kill the process without
# ever hitting Python's own exception machinery, so no traceback normally
# survives them. faulthandler writes a low-level stack dump straight to this
# file the instant a fatal signal (SIGSEGV/SIGABRT/...) fires, which is the
# only way to see what was actually running at the moment of a hard crash.
_CRASH_LOG = Path(__file__).resolve().parent.parent / "logs" / "crash.log"
_CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
_crash_log_file = open(_CRASH_LOG, "a", buffering=1)
faulthandler.enable(file=_crash_log_file, all_threads=True)

# Safety cap so the splash can't hang forever if WSL boot stalls or the
# readiness signal never fires for some other reason.
_SPLASH_MAX_WAIT_MS = 20_000


class _PreflightWorker(QThread):
    """Runs the dependency doctor off the GUI thread — its WSL probes can
    block for seconds on a cold VM, which must never freeze the window. The
    report is delivered back to the main thread via `done` for the dialog."""

    done = Signal(object)  # preflight.Report

    def run(self) -> None:
        try:
            self.done.emit(preflight.run_checks())
        except Exception:  # noqa: BLE001 — a doctor crash must not sink startup
            pass


def _show_preflight_warning(window, report) -> None:
    """Non-blocking: if anything's missing, tell the user what and how to
    fix it, but let them keep using whatever does work. No dialog at all
    when every check passed."""
    body = preflight.format_problems_html(report)
    if not body:
        return
    box = QMessageBox(window)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("TheRecon — setup incomplete")
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(body)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setModal(False)
    box.show()


def _make_splash() -> QSplashScreen:
    pix = QPixmap(440, 220)
    pix.fill(QColor(BG))
    splash = QSplashScreen(pix)
    splash.showMessage(
        f"{WINDOW_TITLE}\n\nStarting up — waiting for WSL...",
        Qt.AlignmentFlag.AlignCenter, QColor(TEXT),
    )
    return splash


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    # ReconMainWindow() below blocks briefly (WSL distro detection) — show a
    # splash so startup doesn't look frozen, PyCharm-style, instead of a
    # blank window appearing after a stall.
    splash = _make_splash()
    splash.show()
    app.processEvents()

    window = ReconMainWindow()
    window.show()

    # Keep the splash up past widget construction, until the Wizard
    # Console's terminal has actually spawned its WSL/bash backend (not
    # just until Python-side __init__ returns) — WSL's own boot can take a
    # few seconds longer than building the widget tree.
    closed = {"done": False}

    def _close_splash():
        if not closed["done"]:
            closed["done"] = True
            splash.finish(window)

    window.main_area.wizard_tab.firstTabReady.connect(_close_splash)
    QTimer.singleShot(_SPLASH_MAX_WAIT_MS, _close_splash)

    # Dependency doctor: check WSL + the 6 tools + both Python runtimes in
    # the background and, only if something's missing, pop a non-blocking
    # warning with the exact fix. Kept as an attribute so the QThread isn't
    # garbage-collected mid-run. Started a beat after show() so it doesn't
    # contend with the terminal's own first WSL boot for the splash window.
    worker = _PreflightWorker()
    worker.done.connect(lambda rep: _show_preflight_warning(window, rep))
    window._preflight_worker = worker
    QTimer.singleShot(2500, worker.start)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
