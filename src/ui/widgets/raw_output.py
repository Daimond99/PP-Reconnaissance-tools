"""RawOutputTab — the display-only surface for Direct Tool Mode Execute
output (read-only terminal backend)."""

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Signal, Qt

from src.config import TEXT_MUTE
from src.ui.terminal_tabs import make_terminal
from src.ui.widgets.helpers import wrap_in_terminal


class RawOutputTab(QWidget):
    """Display-only output surface — same backend the Wizard Console uses
    (XtermTerminal → PtyTerminal → InteractiveTerminal), but with keyboard
    input dropped (`read_only=True`) so it's never typed into directly.
    XtermTerminal narrows that further: input is unlocked for the duration
    of a `run_command()` call and re-locked the instant it reports done, so
    an interactive prompt the gated command itself raises (e.g. `sudo`'s
    password prompt) can be answered without ever exposing a free-typing
    shell. The top-bar Execute button sends its gated command here instead
    of a QMessageBox, so the scan runs with real color/output in a real
    terminal.

    The terminal itself (one QWebEngineView = one Chromium renderer process,
    plus a real wsl.exe/bash PTY) is not spawned until this page is actually
    needed — first shown, or first fed a command — instead of eagerly at app
    startup. `commandDone` is a stable signal owned by this tab (not the
    inner terminal), so callers can connect to it once at construction and
    it keeps working correctly regardless of when the real terminal ends up
    getting created underneath."""

    commandDone = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(0)

        self.terminal = None
        self.console = None
        self._placeholder = QLabel("Idle — display-only, waiting for a command to run here.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {TEXT_MUTE};")
        self._layout.addWidget(self._placeholder, 1)

    def _ensure_terminal(self) -> None:
        if self.terminal is not None:
            return
        self.terminal = make_terminal("shell", read_only=True)
        self.console = self.terminal
        self._layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._placeholder = None
        self._layout.addWidget(wrap_in_terminal(self.terminal), 1)
        done_signal = getattr(self.terminal, "commandDone", None)
        if done_signal is not None:
            done_signal.connect(self.commandDone.emit)

    def showEvent(self, event) -> None:
        self._ensure_terminal()
        super().showEvent(event)

    def run_command(self, command: str):
        """Send an already-gated command into the live shell as if typed.
        Returns a completion token if the backend supports done-detection
        (xterm.js), else None."""
        self._ensure_terminal()
        run = getattr(self.terminal, "run_command", None)
        if callable(run):
            return run(command)
        write = getattr(self.terminal, "write_text", None)
        if callable(write):
            write(command)
        return None

    def interrupt(self) -> None:
        if self.terminal is None:
            return
        interrupt = getattr(self.terminal, "interrupt", None)
        if callable(interrupt):
            interrupt()

    def focus(self) -> None:
        self._ensure_terminal()
        focus = getattr(self.terminal, "focus", None)
        if callable(focus):
            focus()
