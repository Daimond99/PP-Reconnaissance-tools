import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen
from src.config import STYLESHEET, WINDOW_TITLE, BG, TEXT
from src.ui.main_window import ReconMainWindow

# Safety cap so the splash can't hang forever if WSL boot stalls or the
# readiness signal never fires for some other reason.
_SPLASH_MAX_WAIT_MS = 20_000


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

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
