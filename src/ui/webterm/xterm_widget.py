"""
IDE-grade embedded terminal — xterm.js (the same VT emulator VS Code ships)
hosted in a QWebEngineView, driven by a real pseudo-terminal.

Why this instead of the old `PtyTerminal` (pyte → HTML): xterm.js is a mature,
battle-tested emulator that already handles ANSI colour, UTF-8, history reflow
on resize, mouse selection, copy/paste, and full-screen curses apps
(vim/nano/htop/python). We do not re-implement any of that — we only bridge a
real PTY to it.

Architecture
------------
    ┌───────────── Qt (PySide6) ─────────────┐
    │  XtermTerminal(QWidget)                 │
    │    └ QWebEngineView → term.html         │
    │         ▲ bytes (b64)   │ keys / resize │
    │         │   QWebChannel(Bridge)         │
    │    ┌────┴─────────────▼──────┐          │
    │    │  _PtyBackend (QThread)  │          │
    │    │   Win : winpty ConPTY   │  spawns  │
    │    │   Linux: stdlib pty     │  a shell │
    │    └─────────────────────────┘          │
    └─────────────────────────────────────────┘

The PTY layer is the only OS-specific part:
  * Windows → `winpty.PtyProcess` (ConPTY). Used to run `wsl.exe … bash`.
  * Linux   → stdlib `pty`/`os` fork of `/bin/bash` (no third-party dep).

Bytes flow PTY→UI base64-encoded so multi-byte UTF-8 never splits across a
QWebChannel string boundary; xterm.js decodes the Uint8Array itself.
"""

from __future__ import annotations

import base64
import os
import re
import signal
import uuid
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.config import CONSOLE_BG, CONSOLE_TEXT

# QWebEngine / QWebChannel are optional at import time so a machine without the
# WebEngine wheel degrades to the pyte/plain fallbacks instead of crashing.
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebChannel import QWebChannel
    _WEB_OK = True
except Exception:  # pragma: no cover - import guard
    _WEB_OK = False

# A usable PTY backend must exist for the current OS.
_PTY_OK = False
if os.name == "nt":
    try:
        from winpty import PtyProcess  # type: ignore
        _PTY_OK = True
    except Exception:  # pragma: no cover
        _PTY_OK = False
else:
    try:
        import pty  # noqa: F401  (stdlib, POSIX only)
        import fcntl  # noqa: F401
        import termios  # noqa: F401
        import struct  # noqa: F401
        _PTY_OK = True
    except Exception:  # pragma: no cover
        _PTY_OK = False

XTERM_AVAILABLE = _WEB_OK and _PTY_OK

_HERE = Path(__file__).resolve().parent
_TEMPLATE = _HERE / "term.html"


# ───────────────────────────── PTY backends ─────────────────────────────────
class _WinPty:
    """ConPTY-backed PTY via pywinpty."""

    def __init__(self, argv: List[str], cols: int, rows: int):
        self._proc = PtyProcess.spawn(argv, dimensions=(rows, cols))

    def read(self) -> bytes:
        # pywinpty decodes to str; re-encode so the backend speaks bytes.
        data = self._proc.read(65536)
        if not data:
            raise EOFError
        return data.encode("utf-8", "replace")

    def write(self, text: str) -> None:
        self._proc.write(text)

    def resize(self, cols: int, rows: int) -> None:
        self._proc.setwinsize(rows, cols)

    def alive(self) -> bool:
        try:
            return bool(self._proc.isalive())
        except Exception:
            return False

    def terminate(self) -> None:
        try:
            self._proc.terminate(force=True)
        except Exception:
            pass


class _PosixPty:
    """stdlib pty fork of a shell (Linux/macOS) — no third-party dependency."""

    def __init__(self, argv: List[str], cols: int, rows: int):
        self._pid, self._fd = pty.fork()
        if self._pid == 0:  # child
            try:
                os.execvp(argv[0], argv)
            except Exception:
                os._exit(127)
        # parent
        self.resize(cols, rows)

    def read(self) -> bytes:
        data = os.read(self._fd, 65536)
        if not data:
            raise EOFError
        return data

    def write(self, text: str) -> None:
        os.write(self._fd, text.encode("utf-8", "replace"))

    def resize(self, cols: int, rows: int) -> None:
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

    def alive(self) -> bool:
        try:
            pid, _ = os.waitpid(self._pid, os.WNOHANG)
            return pid == 0
        except Exception:
            return False

    def terminate(self) -> None:
        try:
            os.kill(self._pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            os.close(self._fd)
        except Exception:
            pass


def _make_pty(argv: List[str], cols: int, rows: int):
    if os.name == "nt":
        return _WinPty(argv, cols, rows)
    return _PosixPty(argv, cols, rows)


# ───────────────────────────── reader thread ────────────────────────────────
class _Reader(QThread):
    """Blocking PTY reads pumped off the GUI thread; emits raw bytes."""

    dataReady = Signal(bytes)
    closed = Signal()

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._running = True

    def run(self) -> None:
        while self._running:
            try:
                data = self._backend.read()
            except EOFError:
                break
            except Exception:
                break
            if data:
                self.dataReady.emit(data)
        self.closed.emit()

    def stop(self) -> None:
        self._running = False


# ───────────────────────────── JS ↔ Python bridge ───────────────────────────
class _Bridge(QObject):
    """Exposed to the page via QWebChannel as `bridge`."""

    dataToTerm = Signal(str)   # base64 of PTY output → JS term.write

    # emitted after JS calls ready() with the initial geometry
    readySignal = Signal(int, int)
    # emitted on JS resize with new (cols, rows)
    resizeSignal = Signal(int, int)
    # emitted on keystroke / paste text from the terminal
    keySignal = Signal(str)

    @Slot(int, int)
    def ready(self, cols: int, rows: int) -> None:
        self.readySignal.emit(cols, rows)

    @Slot(int, int)
    def resizePty(self, cols: int, rows: int) -> None:
        self.resizeSignal.emit(cols, rows)

    @Slot(str)
    def keyToPty(self, text: str) -> None:
        self.keySignal.emit(text)


# ───────────────────────────── the widget ───────────────────────────────────
class XtermTerminal(QWidget):
    """A real, IDE-grade terminal running `argv` behind xterm.js + a PTY."""

    processFinished = Signal()
    # Emitted when a run_command()-launched command finishes: (token, exit_code).
    commandDone = Signal(str, int)

    _DONE_RE = re.compile(r"__TR_DONE_([0-9a-f]{8})_(-?\d+)__")

    def __init__(self, argv: List[str], cols: int = 110, rows: int = 32, parent=None):
        super().__init__(parent)
        self._argv = argv
        self._cols = cols
        self._rows = rows
        self._backend = None
        self._reader: Optional[_Reader] = None
        self._spawned = False
        self._pending: Optional[str] = None
        self._out_buffer = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.view = QWebEngineView(self)
        # Let the page's JS read/write the system clipboard so Ctrl+C / Ctrl+V
        # (and Ctrl+Shift+C/V) copy/paste work without a permission prompt.
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
        # term.html is a static local page (xterm.js + vendor JS only, no
        # network, no forms, no <video>/<canvas> WebGL) — every renderer
        # subsystem below is dead weight for it. One QWebEngineView (one
        # Chromium renderer process) is spun up per terminal tab, so
        # trimming what each one initializes matters: this is the actual
        # per-tab RAM cost in this app, not anything on the Python side.
        for attr in (
            "PluginsEnabled", "WebGLEnabled", "LocalStorageEnabled",
            "AutoLoadIconsForPage", "HyperlinkAuditingEnabled",
            "ScreenCaptureEnabled", "PdfViewerEnabled", "DnsPrefetchEnabled",
        ):
            web_attr = getattr(QWebEngineSettings.WebAttribute, attr, None)
            if web_attr is not None:
                s.setAttribute(web_attr, False)
        layout.addWidget(self.view, 1)

        self._bridge = _Bridge(self)
        self._bridge.readySignal.connect(self._on_ready)
        self._bridge.resizeSignal.connect(self._on_resize)
        self._bridge.keySignal.connect(self._on_key)

        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self.view.page().setWebChannel(self._channel)

        self._load_page()

    # -- page --------------------------------------------------------------
    def _load_page(self) -> None:
        html = _TEMPLATE.read_text(encoding="utf-8")
        html = html.replace("__BG__", CONSOLE_BG).replace("__FG__", CONSOLE_TEXT)
        # Inject the QWebChannel transport bootstrap. Loading with a file://
        # base URL lets the relative vendor/*.js scripts resolve locally.
        base = QUrl.fromLocalFile(str(_HERE) + os.sep)
        self.view.setHtml(html, base)

    # -- spawn (once JS is ready and sized) --------------------------------
    def _on_ready(self, cols: int, rows: int) -> None:
        if self._spawned:
            return
        self._spawned = True
        self._cols, self._rows = cols, rows
        try:
            self._backend = _make_pty(self._argv, cols, rows)
        except Exception:
            self.processFinished.emit()
            return
        self._reader = _Reader(self._backend, self)
        self._reader.dataReady.connect(self._on_data)
        self._reader.closed.connect(self._on_closed)
        self._reader.start()
        if self._pending:
            try:
                self._backend.write(self._pending)
            except Exception:
                pass
            self._pending = None

    def _on_data(self, data: bytes) -> None:
        b64 = base64.b64encode(data).decode("ascii")
        self._bridge.dataToTerm.emit(b64)
        self._out_buffer = (self._out_buffer + data.decode("utf-8", "replace"))[-4096:]
        m = self._DONE_RE.search(self._out_buffer)
        if m:
            self._out_buffer = ""
            self.commandDone.emit(m.group(1), int(m.group(2)))

    def _on_closed(self) -> None:
        self.processFinished.emit()

    def _on_key(self, text: str) -> None:
        if self._backend:
            try:
                self._backend.write(text)
            except Exception:
                pass

    def _on_resize(self, cols: int, rows: int) -> None:
        self._cols, self._rows = cols, rows
        if self._backend:
            try:
                self._backend.resize(cols, rows)
            except Exception:
                pass

    # -- external command injection (Direct Tool Mode → this terminal) -----
    def write_text(self, text: str) -> None:
        """Inject `text` into the shell as if typed, followed by Enter."""
        if self._backend:
            try:
                self._backend.write(text + "\r")
            except Exception:
                pass
        else:
            self._pending = (self._pending or "") + text + "\r"

    def run_command(self, cmd: str) -> str:
        """Run `cmd` in the shell; emits commandDone(token, exit_code) when
        it finishes. Returns the token."""
        token = uuid.uuid4().hex[:8]
        wrapped = f"{cmd}; printf '__TR_DONE_%s_%d__\\n' {token} $?"
        self.write_text(wrapped)
        return token

    def interrupt(self) -> None:
        if self._backend:
            try:
                self._backend.write("\x03")
            except Exception:
                pass

    def focus(self) -> None:
        """Give the terminal real keyboard focus — Qt widget focus alone
        doesn't focus xterm.js's own hidden textarea, so Ctrl+C typed right
        after switching tabs would otherwise go nowhere."""
        self.view.setFocus()
        self.view.page().runJavaScript("term.focus();")

    # -- teardown ----------------------------------------------------------
    def stop(self) -> None:
        if self._reader:
            self._reader.stop()
        if self._backend:
            try:
                if self._backend.alive():
                    self._backend.terminate()
            except Exception:
                pass

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)
