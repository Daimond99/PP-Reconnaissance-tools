"""
Interactive real-shell terminal widget.

Unlike the read-only log view, this runs a genuine persistent OS shell
(WSL bash on Windows, bash elsewhere) through QProcess and lets the user type
commands directly into the same scrollback view and see real output — a real
terminal, not a mockup, not a chat-style input box bolted underneath it.

It is deliberately generic: pass a different `program`/`args` to launch any
interactive CLI (e.g. `claude` for Claude Code, `llm chat` for an AI chat)
inside the same terminal chrome.
"""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import Qt, QProcess, Signal
from PySide6.QtGui import QFont, QTextCursor, QKeyEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from src.config import CONSOLE_BG, CONSOLE_TEXT


class InteractiveTerminal(QWidget):
    """A live shell terminal backed by a persistent QProcess.

    A single scrollback `QTextEdit` is the whole widget: incoming process
    output is appended to it, and the user types directly at the end of it,
    like a real terminal emulator — no separate input line, no extra chrome.
    """

    processFinished = Signal(int)

    @staticmethod
    def _default_shell():
        """A real bash on both Windows (WSL Ubuntu preferred, then Git Bash)
        and Linux/macOS."""
        if os.name == "nt":
            candidates = [
                ((os.environ.get("BASH_PATH") or ""), ["-i"]),
                ("wsl.exe", []),
                (r"C:\Program Files\Git\bin\bash.exe", ["-i"]),
                (r"C:\Program Files\Git\usr\bin\bash.exe", ["-i"]),
                (r"C:\Windows\System32\bash.exe", ["-i"]),
                ("bash.exe", ["-i"]),
            ]
        else:
            candidates = [(p, ["-i"]) for p in ("/bin/bash", "/usr/bin/bash", "bash")]
        for path, args in candidates:
            if path and (os.path.isfile(path) or os.sep not in path):
                return path, args
        return "bash", ["-i"]

    def __init__(self, program: Optional[str] = None,
                 args: Optional[List[str]] = None,
                 parent=None):
        super().__init__(parent)
        self._program = program
        self._args = args
        self._proc: Optional[QProcess] = None
        self._history: List[str] = []
        self._history_index = 0
        self._input_start = 0  # cursor position where the editable line begins

        self._build()
        self._start_shell()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.output = QTextEdit()
        self.output.setReadOnly(False)
        self.output.setAcceptRichText(False)
        self.output.setFont(font)
        self.output.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; padding: 14px 16px;
            font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;
        """)
        self.output.installEventFilter(self)
        layout.addWidget(self.output, 1)

    # --------------------------------------------------------------- shell
    def _start_shell(self) -> None:
        program = self._program
        args = self._args
        if program is None:
            program, args = self._default_shell()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_output)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)
        self._proc.start(program, args or [])

    def _read_output(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self._append(data)

    def _current_input(self) -> str:
        cursor = self.output.textCursor()
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        return cursor.selectedText()

    def _replace_input(self, text: str) -> None:
        cursor = self.output.textCursor()
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)

    def _send_command(self) -> None:
        cmd = self._current_input()
        if cmd.strip():
            self._history.append(cmd)
        self._history_index = len(self._history)
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n")
        self.output.setTextCursor(cursor)
        self._input_start = cursor.position()
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.write((cmd + "\n").encode("utf-8"))
        else:
            self._append("[terminal not running — restarting shell]\n")
            self._start_shell()

    def _on_finished(self, exit_code: int, _status) -> None:
        self._append(f"\n[shell exited with code {exit_code}]\n")
        self.processFinished.emit(exit_code)

    def _on_error(self, error) -> None:
        self._append(f"\n[!] Failed to start shell ({error})\n")

    # --------------------------------------------------------------- helpers
    def _append(self, text: str) -> None:
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._input_start = cursor.position()
        self.output.setTextCursor(cursor)
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def append_log(self, text: str) -> None:
        """Inject external (already-gated) command output into the view."""
        self._append(text + "\n")

    def eventFilter(self, obj, event):
        if obj is self.output and event.type() == event.Type.KeyPress:
            return self._handle_key(event)
        return super().eventFilter(obj, event)

    def _handle_key(self, event: QKeyEvent) -> bool:
        cursor = self.output.textCursor()
        key = event.key()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._send_command()
            return True
        if key == Qt.Key_Up:
            self._recall(-1)
            return True
        if key == Qt.Key_Down:
            self._recall(1)
            return True
        if key in (Qt.Key_Backspace, Qt.Key_Left) and cursor.position() <= self._input_start:
            return True
        if key == Qt.Key_Home:
            cursor.setPosition(
                self._input_start,
                QTextCursor.MoveMode.KeepAnchor if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                else QTextCursor.MoveMode.MoveAnchor,
            )
            self.output.setTextCursor(cursor)
            return True
        if cursor.position() < self._input_start or (
            cursor.hasSelection() and cursor.selectionStart() < self._input_start
        ):
            cursor.setPosition(self._input_start)
            self.output.setTextCursor(cursor)
        return False

    def _recall(self, step: int) -> None:
        if not self._history:
            return
        self._history_index = max(0, min(len(self._history), self._history_index + step))
        if self._history_index >= len(self._history):
            self._replace_input("")
        else:
            self._replace_input(self._history[self._history_index])

    def stop(self) -> None:
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
