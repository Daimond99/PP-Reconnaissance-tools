"""
Real pseudo-terminal (PTY) widget.

Unlike `InteractiveTerminal` (a plain QProcess pipe that cannot render ANSI
colors and gives child programs no controlling TTY), this embeds a genuine
Windows pseudo-console via ConPTY (pywinpty) and interprets the VT/ANSI output
stream with a real terminal emulator (pyte). The child — e.g. `wsl.exe -d
Ubuntu ... python3 -m wizard.main` — therefore behaves exactly as it would in a
standalone Ubuntu WSL terminal: full color, working `sudo` password prompts,
readline/TAB completion, cursor addressing, the lot.

Layers:
  ConPTY (pywinpty.PtyProcess)  ── raw bytes ──▶  pyte.Screen (VT emulator)
        ▲                                              │
        │ keystrokes (Qt → VT input)                   ▼ rendered as HTML
        └──────────────────────────────────────  QTextEdit view
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QTextOption
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from src.config import CONSOLE_BG, CONSOLE_TEXT

try:
    import pyte
    from winpty import PtyProcess
    PTY_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    PTY_AVAILABLE = False


# ── 16-color ANSI palette (VS Code "Dark+" values) ───────────────────────────
_NAMED = {
    "black": "#1e1e1e", "red": "#cd3131", "green": "#0dbc79", "brown": "#e5e510",
    "yellow": "#e5e510", "blue": "#2472c8", "magenta": "#bc3fbc",
    "cyan": "#11a8cd", "white": "#cccccc",
    "brightblack": "#666666", "brightred": "#f14c4c", "brightgreen": "#23d18b",
    "brightyellow": "#f5f543", "brightblue": "#3b8eea", "brightmagenta": "#d670d6",
    "brightcyan": "#29b8db", "brightwhite": "#ffffff",
}


def _resolve_color(name: str, default: str, bold: bool) -> str:
    """Map a pyte color token (name or 6-hex) to a CSS color."""
    if not name or name == "default":
        return default
    if bold and name in _NAMED and ("bright" + name) in _NAMED:
        name = "bright" + name
    if name in _NAMED:
        return _NAMED[name]
    if len(name) == 6:
        try:
            int(name, 16)
            return "#" + name
        except ValueError:
            pass
    return default


def _esc(ch: str) -> str:
    if ch == "&":
        return "&amp;"
    if ch == "<":
        return "&lt;"
    if ch == ">":
        return "&gt;"
    if ch == " ":
        return "&nbsp;"
    return ch


class _Reader(QThread):
    """Background reader — ConPTY reads block, so pump them off the GUI thread."""

    dataReady = Signal(str)
    closed = Signal()

    def __init__(self, proc: "PtyProcess", parent=None):
        super().__init__(parent)
        self._proc = proc
        self._running = True

    def run(self) -> None:
        while self._running:
            try:
                data = self._proc.read(65536)
            except EOFError:
                break
            except Exception:
                break
            if data:
                self.dataReady.emit(data)
        self.closed.emit()

    def stop(self) -> None:
        self._running = False


class PtyTerminal(QWidget):
    """A colored, TTY-backed terminal that runs an arbitrary command via ConPTY."""

    processFinished = Signal()

    def __init__(self, argv: List[str], cols: int = 110, rows: int = 32, parent=None):
        super().__init__(parent)
        self._argv = argv
        self._cols = cols
        self._rows = rows
        self._proc: Optional["PtyProcess"] = None
        self._reader: Optional[_Reader] = None
        self._dirty = False

        self._build()

        # VT emulator screen + parser
        self._screen = pyte.Screen(cols, rows)
        self._stream = pyte.ByteStream(self._screen) if hasattr(pyte, "ByteStream") \
            else pyte.Stream(self._screen)
        self._feed_is_bytes = hasattr(pyte, "ByteStream")

        # repaint throttle
        self._repaint = QTimer(self)
        self._repaint.setInterval(33)
        self._repaint.timeout.connect(self._flush)
        self._repaint.start()

        # Spawn is deferred to showEvent: only once the widget is laid out do we
        # know its real pixel size, so the PTY (and the child's COLS/LINES) can
        # be sized to fill the pane from the very first line printed. Spawning in
        # __init__ would size the terminal to a stale default and the banner
        # would print pre-wrapped (pyte does not reflow history on resize).
        self._spawned = False

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = QFont()
        # Consolas ships with Windows; the others are graceful fallbacks. Using a
        # guaranteed monospace font is what keeps char-cell metrics correct, so
        # the computed column count matches the real terminal width (no wrapping).
        font.setFamilies(["Consolas", "Cascadia Mono", "Courier New", "monospace"])
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        font.setFixedPitch(True)

        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(font)
        self.view.document().setDocumentMargin(0)
        self.view.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.view.setStyleSheet(
            f"background-color:{CONSOLE_BG}; color:{CONSOLE_TEXT};"
            "border:none; padding:4px 6px;"
        )
        self.view.installEventFilter(self)
        layout.addWidget(self.view, 1)

    # --------------------------------------------------------------- process
    def _spawn(self) -> None:
        self._proc = PtyProcess.spawn(self._argv, dimensions=(self._rows, self._cols))
        self._reader = _Reader(self._proc, self)
        self._reader.dataReady.connect(self._on_data)
        self._reader.closed.connect(self._on_closed)
        self._reader.start()
        self.view.setFocus()

    def _on_data(self, data: str) -> None:
        try:
            if self._feed_is_bytes:
                self._stream.feed(data.encode("utf-8", "replace"))
            else:
                self._stream.feed(data)
        except Exception:
            pass
        self._dirty = True

    def _on_closed(self) -> None:
        self._dirty = True
        self.processFinished.emit()

    # --------------------------------------------------------------- render
    def _flush(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        self.view.setHtml(self._render_html())
        # keep the view pinned to the bottom
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _render_html(self) -> str:
        screen = self._screen
        default_fg = CONSOLE_TEXT
        default_bg = CONSOLE_BG
        out: List[str] = [
            f'<pre style="margin:0;font-family:Consolas,\'Cascadia Mono\',monospace;'
            f'color:{default_fg};white-space:pre">'
        ]
        buf = screen.buffer
        for y in range(screen.lines):
            row = buf[y]
            spans: List[str] = []
            run_chars: List[str] = []
            run_key = None

            def close_run():
                if run_key is None:
                    return
                fg, bg, bold, underscore = run_key
                style = f"color:{fg}"
                if bg != default_bg:
                    style += f";background-color:{bg}"
                if bold:
                    style += ";font-weight:bold"
                if underscore:
                    style += ";text-decoration:underline"
                spans.append(f'<span style="{style}">{"".join(run_chars)}</span>')

            for x in range(screen.columns):
                char = row[x]
                fg = _resolve_color(char.fg, default_fg, char.bold)
                bg = _resolve_color(char.bg, default_bg, False)
                if char.reverse:
                    fg, bg = bg, fg
                key = (fg, bg, char.bold, char.underscore)
                if key != run_key:
                    close_run()
                    run_key = key
                    run_chars = []
                run_chars.append(_esc(char.data or " "))
            close_run()
            out.append("".join(spans))
            if y != screen.lines - 1:
                out.append("\n")
        out.append("</pre>")
        return "".join(out)

    # --------------------------------------------------------------- input
    def eventFilter(self, obj, event):
        if obj is self.view and event.type() == event.Type.KeyPress:
            self._send_key(event)
            return True
        return super().eventFilter(obj, event)

    def _send_key(self, event: QKeyEvent) -> None:
        if not self._proc:
            return
        key = event.key()
        mods = event.modifiers()
        seq = None

        specials = {
            Qt.Key_Return: "\r", Qt.Key_Enter: "\r",
            Qt.Key_Backspace: "\x7f", Qt.Key_Tab: "\t",
            Qt.Key_Escape: "\x1b",
            Qt.Key_Up: "\x1b[A", Qt.Key_Down: "\x1b[B",
            Qt.Key_Right: "\x1b[C", Qt.Key_Left: "\x1b[D",
            Qt.Key_Home: "\x1b[H", Qt.Key_End: "\x1b[F",
            Qt.Key_PageUp: "\x1b[5~", Qt.Key_PageDown: "\x1b[6~",
            Qt.Key_Delete: "\x1b[3~",
        }

        if (mods & Qt.KeyboardModifier.ControlModifier) and Qt.Key_A <= key <= Qt.Key_Z:
            seq = chr(key - Qt.Key_A + 1)  # Ctrl-A..Ctrl-Z → 0x01..0x1a
        elif key in specials:
            seq = specials[key]
        elif event.text():
            seq = event.text()

        if seq:
            try:
                self._proc.write(seq)
            except Exception:
                pass

    # --------------------------------------------------------------- sizing
    def _fit(self) -> tuple[int, int]:
        """Compute (cols, rows) that fill the current viewport at the cell size."""
        fm = self.view.fontMetrics()
        char_w = max(1, fm.horizontalAdvance("M"))
        char_h = max(1, fm.lineSpacing())
        vp = self.view.viewport().size()
        cols = max(20, vp.width() // char_w)
        rows = max(6, vp.height() // char_h)
        return cols, rows

    def showEvent(self, event):
        super().showEvent(event)
        if not self._spawned:
            self._spawned = True
            # Defer one event-loop turn so the layout settles to its final
            # width before we size the PTY — otherwise the child prints its
            # banner at a stale (narrow) column count and pyte won't reflow it.
            QTimer.singleShot(0, self._deferred_spawn)

    def _deferred_spawn(self) -> None:
        self._cols, self._rows = self._fit()
        try:
            self._screen.resize(self._rows, self._cols)
        except Exception:
            pass
        self._spawn()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._spawned:
            return
        cols, rows = self._fit()
        if cols == self._cols and rows == self._rows:
            return
        self._cols, self._rows = cols, rows
        try:
            self._screen.resize(rows, cols)
            if self._proc:
                self._proc.setwinsize(rows, cols)
            self._dirty = True
        except Exception:
            pass

    # --------------------------------------------------------------- teardown
    def stop(self) -> None:
        if self._reader:
            self._reader.stop()
        if self._proc:
            try:
                if self._proc.isalive():
                    self._proc.terminate(force=True)
            except Exception:
                pass
