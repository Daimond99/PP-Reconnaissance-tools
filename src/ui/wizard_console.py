"""
Interactive Wizard Console tab — guided shell with QProcess execution.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QProcess, Signal
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QKeyEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from src.config import TERMINAL_FONT_FAMILY, CONSOLE_BG, CONSOLE_TEXT
from src.wizard.engine import WizardEngine, WizardStep
from src.validation.common import parse_command_line
from src.core.tool_manager import get_tool_manager


class WizardConsoleTab(QWidget):
    """Interactive guided shell wizard with QProcess execution."""

    commandEntered = Signal(str)
    executionStarted = Signal()
    executionFinished = Signal()

    ERROR_COLOR = "#ff5555"
    SUCCESS_COLOR = "#50fa7b"
    INFO_COLOR = "#8be9fd"
    WARN_COLOR = "#f1fa8c"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.wizard_engine = WizardEngine()
        self.tool_manager = get_tool_manager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = QFont(TERMINAL_FONT_FAMILY, 11)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(False)
        self.output_area.setAcceptRichText(False)
        self.output_area.setFont(font)
        self.output_area.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; border-radius: 4px; padding: 30px 35px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
            line-height: 150%;
        """)
        layout.addWidget(self.output_area, 1)
        self.console = self.output_area

        self._history: list[str] = []
        self._history_index = -1
        self._draft_input = ""
        self._prompt_label = "Select>"
        self._input_enabled = True
        self._input_start_pos = 0

        self._process: QProcess | None = None
        self._command_queue: list[str] = []
        self._current_command = ""

        self._original_key_handler = self.output_area.keyPressEvent
        self.output_area.keyPressEvent = self._on_key_press

        self._boot_wizard()

    def _boot_wizard(self) -> None:
        result = self.wizard_engine.reset()
        self._render_result(result, clear=True)

    def _on_key_press(self, event: QKeyEvent) -> None:
        if not self._input_enabled:
            if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                self.cancel_execution()
            return

        key = event.key()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._submit_current_line()
            return

        if key == Qt.Key_Backspace:
            if self.output_area.textCursor().position() <= self._input_start_pos:
                return
            self._original_key_handler(event)
            return

        if key == Qt.Key_Left:
            if self.output_area.textCursor().position() <= self._input_start_pos:
                return
            self._original_key_handler(event)
            return

        if key == Qt.Key_Up:
            self._history_prev()
            return

        if key == Qt.Key_Down:
            self._history_next()
            return

        if key == Qt.Key_Home:
            cursor = self.output_area.textCursor()
            cursor.setPosition(self._input_start_pos)
            self.output_area.setTextCursor(cursor)
            return

        if key in (Qt.Key_PageUp, Qt.Key_PageDown):
            self._original_key_handler(event)
            return

        cursor = self.output_area.textCursor()
        if cursor.position() < self._input_start_pos:
            cursor.setPosition(self._input_start_pos)
            self.output_area.setTextCursor(cursor)

        self._original_key_handler(event)

    def _submit_current_line(self) -> None:
        text = self._current_input()
        self._append_newline()

        # At the SUGGESTION step, an empty Enter is a valid answer (it means
        # "use the auto-suggested command") and must reach the wizard engine.
        accept_empty = self.wizard_engine.state.current_step == WizardStep.SUGGESTION

        if text or accept_empty:
            if text:
                self._history.append(text)
                self._history_index = len(self._history)
            self._draft_input = ""
            self._handle_user_input(text)
        else:
            self._show_prompt(self._prompt_label)

    def _current_input(self) -> str:
        full = self.output_area.toPlainText()
        if len(full) < self._input_start_pos:
            return ""
        return full[self._input_start_pos:]

    def _set_input_text(self, text: str) -> None:
        cursor = self.output_area.textCursor()
        cursor.setPosition(self._input_start_pos)
        cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    def _history_prev(self) -> None:
        if not self._history:
            return
        if self._history_index == len(self._history):
            self._draft_input = self._current_input()
        if self._history_index > 0:
            self._history_index -= 1
            self._set_input_text(self._history[self._history_index])

    def _history_next(self) -> None:
        if not self._history:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._set_input_text(self._history[self._history_index])
        else:
            self._history_index = len(self._history)
            self._set_input_text(self._draft_input)

    def _append_newline(self) -> None:
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n")
        self.output_area.setTextCursor(cursor)

    def _append_line(self, text: str, color: str | None = None) -> None:
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if color:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
        else:
            cursor.setCharFormat(QTextCharFormat())
        cursor.insertText(text + "\n")
        self.output_area.setTextCursor(cursor)

    def _append_raw(self, text: str) -> None:
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.setCharFormat(QTextCharFormat())
        cursor.insertText(text)
        self.output_area.setTextCursor(cursor)

    def _show_prompt(self, label: str) -> None:
        self._prompt_label = label or "Select>"
        if label:
            self._append_raw(f"{label} ")
        self._input_start_pos = len(self.output_area.toPlainText())
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    def _render_result(self, result, clear: bool = False) -> None:
        if clear:
            self.output_area.clear()

        for line in result.lines:
            if line == "__SHOW_TOOL_STATUS__":
                self._print_tool_status()
                continue
            if line == "__SHOW_INSTALL_GUIDE__":
                self._print_install_guide()
                continue
            color = None
            if line.startswith("[!]") or line.startswith("Error"):
                color = self.ERROR_COLOR
            elif line.startswith("[+]"):
                color = self.SUCCESS_COLOR
            elif line.startswith("[*]"):
                color = self.INFO_COLOR
            elif line.startswith("⚠"):
                color = self.WARN_COLOR
            self._append_line(line, color)

        if result.prompt:
            self._show_prompt(result.prompt)

        if result.action == "execute":
            chain = " && ".join(result.commands)
            self.commandEntered.emit(chain)
            self._start_command_chain(result.commands)
        elif result.action == "cancel":
            self.cancel_execution()

    def _handle_user_input(self, text: str) -> None:
        result = self.wizard_engine.handle_input(text)
        if not result.success and result.lines:
            self._append_line(result.lines[0], self.ERROR_COLOR)
            for extra in result.lines[1:]:
                self._append_line(extra)
            self._show_prompt(result.prompt or self._prompt_label)
            return
        self._render_result(result)

    def _print_tool_status(self) -> None:
        for _tool_name, (installed, status) in self.tool_manager.get_all_status().items():
            color = self.SUCCESS_COLOR if installed else self.ERROR_COLOR
            for subline in status.split("\n"):
                self._append_line(subline, color)

    def _print_install_guide(self) -> None:
        missing = self.tool_manager.get_missing_tools()
        if not missing:
            self._append_line("All tracked tools are installed.", self.SUCCESS_COLOR)
            return
        for tool_name in missing:
            guide = self.tool_manager.get_install_guide(tool_name)
            tool_info = self.tool_manager.get_tool_info(tool_name)
            self._append_line(f"{tool_info.display_name}:", self.WARN_COLOR)
            for line in guide.split("\n"):
                self._append_line(f"  {line}")

    def _set_input_enabled(self, enabled: bool) -> None:
        self._input_enabled = enabled
        self.output_area.setReadOnly(not enabled)

    def _start_command_chain(self, commands: list[str]) -> None:
        if not commands:
            return
        self._command_queue = list(commands)
        self._set_input_enabled(False)
        self.executionStarted.emit()
        self._run_next_command()

    def _run_next_command(self) -> None:
        if not self._command_queue:
            self._on_chain_finished()
            return

        command = self._command_queue.pop(0)
        ok, err, argv = parse_command_line(command)
        if not ok:
            self._append_line(f"[!] Rejected command: {err}", self.ERROR_COLOR)
            self._on_chain_finished()
            return

        self._current_command = command
        program, args = argv[0], argv[1:]
        self._append_line(f"[*] Running: {command}", self.INFO_COLOR)

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.start(program, args)

    def _read_stdout(self) -> None:
        if not self._process:
            return
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stream_process_output(data)

    def _read_stderr(self) -> None:
        if not self._process:
            return
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stream_process_output(data, self.WARN_COLOR)

    def _stream_process_output(self, data: str, color: str | None = None) -> None:
        if not data:
            return
        for line in data.splitlines(keepends=True):
            if line.endswith("\n") or line.endswith("\r"):
                self._append_line(line.rstrip("\r\n"), color)
            else:
                self._append_raw(line)

    def _on_process_finished(self, exit_code: int, _exit_status) -> None:
        self._append_line(f"[*] Process exited with code {exit_code}", self.INFO_COLOR)
        self._process = None
        self._run_next_command()

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._append_line("[!] Failed to start process. Is the tool installed?", self.ERROR_COLOR)
            self._command_queue.clear()
            self._on_chain_finished()

    def _on_chain_finished(self) -> None:
        self._set_input_enabled(True)
        self.executionFinished.emit()
        result = self.wizard_engine.execution_finished()
        self._render_result(result)

    def cancel_execution(self) -> None:
        was_running = self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning
        if was_running:
            self._append_line("^C")
            self._append_line("[!] Process ถูกยกเลิกโดยผู้ใช้", self.ERROR_COLOR)
            self._process.kill()
            self._process = None
        self._command_queue.clear()
        if was_running or not self._input_enabled:
            # Log cancellation to audit and reset wizard state with proper message
            self._set_input_enabled(True)
            self.executionFinished.emit()
            result = self.wizard_engine.handle_cancelled()
            self._render_result(result)

    def is_running(self) -> bool:
        return (
            not self._input_enabled
            or (
                self._process is not None
                and self._process.state() != QProcess.ProcessState.NotRunning
            )
        )

    def write_output(self, text: str) -> None:
        self._append_line(text)

    def reset_wizard(self) -> None:
        if self.is_running():
            self.cancel_execution()
        self._history.clear()
        self._history_index = -1
        self._draft_input = ""
        result = self.wizard_engine.reset()
        self._render_result(result, clear=True)

    # Backward-compatible hooks used by main_window
    def _show_initial_menu(self) -> None:
        self.reset_wizard()

    def _clear_output(self) -> None:
        self.output_area.clear()
