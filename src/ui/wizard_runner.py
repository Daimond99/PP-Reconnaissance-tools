"""
WizardRunner — connects `WizardControlPanel.scanRequested` to a
`WizardDriver` and answers its signals with the dialogs in
`wizard_dialogs.py`, so a wizard run is entirely Qt widgets end to end (no
terminal tab, no raw text typed anywhere). Two views sit side by side under a
tab bar:
  - `WizardProgressView` — one table row per structured status event (scan
    result / step outcome / credential found / summary), same shape for
    every tool in the chain. Searchable and filterable by row type.
  - `WizardRawOutputView` — the wizard subprocess's actual captured command
    output (nmap/hydra/... stdout, echoed via `core.display`).

Every run is recorded in `ScanHistory` as it happens, so a run that is closed
mid-way keeps the rows it had produced, and a past run can be reopened from
the History dialog without running anything again.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTabBar, QVBoxLayout, QWidget,
)

from src.config import (
    BG_INPUT, BORDER, BORDER_SOFT, CONSOLE_BG, CONSOLE_TEXT, PANEL,
    PURPLE, PURPLE_DIM, TERM_MUTE, TERMINAL_FONT_FAMILY, TEXT, TEXT_DIM,
)
from src.core import scan_history as history_store
from src.core.scan_history import ScanHistory
from src.core.wizard_driver import WizardDriver
from src.ui import wizard_dialogs as dialogs
from src.ui.log_viewer import LogViewerDialog, find_logs
from src.ui.terminal_launch import _TOOL_CONTAINER, _repo_local_dir

_COLUMNS = ["Type", "Target", "Tool", "Detail", "Status"]
_ROW_TYPES = ["All", "Scan", "Step", "Credential", "Summary", "Info", "Finished", "Error"]
_HISTORY_COLUMNS = ["Started", "Target", "Status", "Rows", "Exit code"]
_STATUS_LABELS = {
    history_store.RUNNING: "Running",
    history_store.FINISHED: "Finished",
    history_store.STOPPED: "Stopped",
    history_store.FAILED: "Failed",
    history_store.INTERRUPTED: "Interrupted",
}


def _scan_result_row(data: dict, text: str) -> tuple[str, str, str, str, str]:
    port, service = data.get("port", "-"), data.get("service", "-")
    return "Scan", f"{port}/tcp", "-", service, "Open"


def _step_start_row(data: dict, text: str) -> tuple[str, str, str, str, str]:
    port, service = data.get("port", "-"), data.get("service", "-")
    tool, name = data.get("tool", "-"), data.get("name", "-")
    return "Step", f"{port}/{service}", tool, name, "Running"


def _step_done_row(data: dict, text: str) -> tuple[str, str, str, str, str]:
    port, service = data.get("port", "-"), data.get("service", "-")
    tool, name = data.get("tool", "-"), data.get("name", "-")
    outcome = data.get("outcome", "-").capitalize()
    return "Step", f"{port}/{service}", tool, name, outcome


def _cred_found_row(data: dict, text: str) -> tuple[str, str, str, str, str]:
    port, service = data.get("port", "-"), data.get("service", "-")
    user, password = data.get("user", "-"), data.get("password", "-")
    return "Credential", f"{port}/{service}", "-", f"{user}:{password}", "Found"


def _summary_row(data: dict, text: str) -> tuple[str, str, str, str, str]:
    executed, skipped = data.get("executed", "-"), data.get("skipped", "-")
    return "Summary", "-", "-", f"Executed {executed} · Skipped {skipped}", "-"


_ROW_BUILDERS = {
    "scan_result": _scan_result_row,
    "step_start": _step_start_row,
    "step_done": _step_done_row,
    "cred_found": _cred_found_row,
    "summary": _summary_row,
}


def status_row(message: dict) -> tuple[str, ...]:
    builder = _ROW_BUILDERS.get(message.get("kind", ""))
    if builder is None:
        return ("Info", "-", "-", message.get("text", ""), "-")
    return builder(message.get("data", {}) or {}, message.get("text", ""))


def _matches(row: tuple[str, ...], row_type: str, needle: str) -> bool:
    if row_type != "All" and row[0] != row_type:
        return False
    return not needle or needle in " ".join(row).lower()


class WizardProgressView(QWidget):
    """Table of structured status rows. Keeps every row in memory so the
    search box and type filter can redraw the table without losing data."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("WizProgress")
        self._rows: list[tuple[str, ...]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._banner = QLabel()
        self._banner.setObjectName("WizProgressBanner")
        self._banner.setWordWrap(True)
        self._banner.setVisible(False)
        root.addWidget(self._banner)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(10, 8, 10, 8)
        filter_row.setSpacing(8)
        self._search = QLineEdit()
        self._search.setObjectName("MissionInput")
        self._search.setPlaceholderText("Search rows…")
        self._search.setClearButtonEnabled(True)
        self._type = QComboBox()
        self._type.setObjectName("WizTypeFilter")
        self._type.addItems(_ROW_TYPES)
        self._search.textChanged.connect(self._render)
        self._type.currentIndexChanged.connect(self._render)
        filter_row.addWidget(self._search, 1)
        filter_row.addWidget(self._type)
        root.addLayout(filter_row)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._empty = QLabel(
            "Fill in the panel on the left and press Start scan.\n"
            "Every menu and confirmation appears as a dialog here — no "
            "terminal, no typed commands.")
        self._empty.setObjectName("WizProgressEmpty")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setObjectName("WizProgressTable")
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        for col in (0, 1, 2, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._table)
        self._stack.setCurrentWidget(self._empty)

        self.setStyleSheet(f"""
            QLabel#WizProgressEmpty {{
                background: {PANEL}; color: {TEXT_DIM}; border: none;
                padding: 24px; font-size: 13px;
            }}
            QLabel#WizProgressBanner {{
                background: {BG_INPUT}; color: {TEXT}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 8px 10px; font-size: 12px;
            }}
            QComboBox#WizTypeFilter {{
                background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 6px 10px; min-width: 110px;
            }}
            QTableWidget#WizProgressTable {{
                background: {PANEL}; color: {TEXT}; border: none;
                gridline-color: {BORDER};
            }}
            QTableWidget#WizProgressTable::item {{
                padding: 6px 10px; border-bottom: 1px solid {BORDER};
            }}
            QHeaderView::section {{
                background: {BG_INPUT}; color: {TEXT_DIM}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 6px 10px;
            }}
        """)

    def add_row(self, cells: tuple[str, ...]) -> None:
        self._rows.append(tuple(str(cell) for cell in cells))
        self._render(follow=True)

    def append(self, text: str) -> None:
        self.add_row(("Info", "-", "-", text, "-"))

    def status(self, message: dict) -> None:
        self.add_row(status_row(message))

    def finished(self, exit_code: int) -> None:
        self.add_row(("Finished", "-", "-", f"exit code {exit_code}", "-"))

    def error(self, text: str) -> None:
        self.add_row(("Error", "-", "-", text, "Error"))

    def show_saved(self, rows: list[list[str]], banner: str) -> None:
        self._rows = [tuple(row) for row in rows]
        self._banner.setText(banner)
        self._banner.setVisible(True)
        self._search.blockSignals(True)
        self._type.blockSignals(True)
        self._search.clear()
        self._type.setCurrentIndex(0)
        self._search.blockSignals(False)
        self._type.blockSignals(False)
        self._render()

    def clear(self) -> None:
        self._rows = []
        self._banner.setVisible(False)
        self._search.blockSignals(True)
        self._type.blockSignals(True)
        self._search.clear()
        self._type.setCurrentIndex(0)
        self._search.blockSignals(False)
        self._type.blockSignals(False)
        self._table.setRowCount(0)
        self._stack.setCurrentWidget(self._empty)

    def _render(self, follow: bool = False) -> None:
        if not self._rows:
            self._table.setRowCount(0)
            self._stack.setCurrentWidget(self._empty)
            return
        needle = self._search.text().strip().lower()
        row_type = self._type.currentText()
        visible = [row for row in self._rows if _matches(row, row_type, needle)]
        self._table.setRowCount(0)
        for row_index, cells in enumerate(visible):
            self._table.insertRow(row_index)
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._table.setItem(row_index, col, item)
        self._stack.setCurrentWidget(self._table)
        if follow:
            self._table.scrollToBottom()


class WizardRawOutputView(QWidget):
    """Read-only viewer for the wizard subprocess's real captured command
    output (nmap/hydra/... stdout as echoed by `core.display`)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._text = QPlainTextEdit()
        self._text.setObjectName("WizRawOutput")
        self._text.setReadOnly(True)
        self._text.setPlaceholderText(
            "Captured command output (nmap/hydra/...) appears here once a "
            "scan is running.")
        root.addWidget(self._text)

        self.setStyleSheet(f"""
            QPlainTextEdit#WizRawOutput {{
                background: {BG_INPUT}; color: {TEXT}; border: none;
                padding: 10px; font-family: {TERMINAL_FONT_FAMILY}, monospace;
            }}
        """)

    def clear(self) -> None:
        self._text.clear()

    def append_chunk(self, text: str) -> None:
        cursor = self._text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()


def _chain_dir() -> Path:
    return Path(_repo_local_dir())


def _chain_relpath(path: Path) -> str:
    try:
        return Path(os.path.relpath(path, _chain_dir())).as_posix()
    except ValueError:
        return path.as_posix()


_DIALOG_QSS_TEMPLATE = f"""
    QDialog {{ background: {PANEL}; }}
    QLabel {{ color: {TEXT_DIM}; font-size: 11px; }}
    QPlainTextEdit, QTableWidget {{
        background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
        padding: 6px; font-family: {TERMINAL_FONT_FAMILY}, monospace;
    }}
    QHeaderView::section {{
        background: {BG_INPUT}; color: {TEXT_DIM}; border: none;
        border-bottom: 1px solid {BORDER}; padding: 6px 10px;
    }}
    QPushButton {{
        background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
        border-radius: 6px; padding: 7px 14px;
    }}
    QPushButton:hover {{ border: 1px solid {PURPLE_DIM}; }}
"""


class _HistoryDialog(QDialog):
    def __init__(self, history: ScanHistory, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Scan history")
        self.resize(820, 440)
        self.setStyleSheet(_DIALOG_QSS_TEMPLATE)
        self.selected_id: str | None = None
        self.selected_action = "open"

        self._history = history
        self._runs = history.runs()
        root = QVBoxLayout(self)
        table = QTableWidget(len(self._runs), len(_HISTORY_COLUMNS))
        table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        for row_index, run in enumerate(self._runs):
            cells = (run.started, run.target, _STATUS_LABELS.get(run.status, run.status),
                     str(len(run.rows)), "-" if run.exit_code is None else str(run.exit_code))
            for col, value in enumerate(cells):
                table.setItem(row_index, col, QTableWidgetItem(value))
        table.currentCellChanged.connect(lambda *_args: self._refresh_buttons())
        table.itemDoubleClicked.connect(lambda _item: self._choose("open"))
        self._table = table
        root.addWidget(table, 1)

        if not self._runs:
            root.addWidget(QLabel("No scans recorded yet. Run a scan and it will appear here."))

        buttons = QDialogButtonBox()
        self._open_btn = buttons.addButton("Open", QDialogButtonBox.ButtonRole.AcceptRole)
        self._open_btn.clicked.connect(lambda: self._choose("open"))
        self._resume_btn = buttons.addButton("Resume scan", QDialogButtonBox.ButtonRole.ActionRole)
        self._resume_btn.clicked.connect(lambda: self._choose("resume"))
        buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(self.reject)
        root.addWidget(buttons)
        if self._runs:
            table.setCurrentCell(0, 0)
        self._refresh_buttons()

    def _selected_run(self) -> history_store.Run | None:
        index = self._table.currentRow()
        if 0 <= index < len(self._runs):
            return self._runs[index]
        return None

    def _refresh_buttons(self) -> None:
        run = self._selected_run()
        self._open_btn.setEnabled(run is not None)
        self._resume_btn.setEnabled(run is not None and self._history.resumable(run))

    def _choose(self, action: str) -> None:
        run = self._selected_run()
        if run is None or (action == "resume" and not self._history.resumable(run)):
            return
        self.selected_id = run.id
        self.selected_action = action
        self.accept()


_RAW_OUTPUT_NOTE = "Raw output is not kept for saved runs. Use View log for the full text."


class WizardRunner(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._history = ScanHistory()
        self._history.mark_interrupted()
        self._run: history_store.Run | None = None
        self._stop_requested = False

        self.progress = WizardProgressView()
        self.raw_output = WizardRawOutputView()
        self._log_path: Path | None = None

        tabbar = QTabBar()
        tabbar.setObjectName("WizRunnerTabBar")
        tabbar.addTab("Progress")
        tabbar.addTab("Raw Output")
        tabbar.setDrawBase(False)
        tabbar.setExpanding(False)

        stack = QStackedWidget()
        stack.addWidget(self.progress)
        stack.addWidget(self.raw_output)
        tabbar.currentChanged.connect(stack.setCurrentIndex)

        self._history_btn = QPushButton("History")
        self._history_btn.setObjectName("WizRunnerLogBtn")
        self._history_btn.setToolTip("Reopen a past scan without running it again")
        self._history_btn.clicked.connect(self._show_history)

        self._log_btn = QPushButton("View log")
        self._log_btn.setObjectName("WizRunnerLogBtn")
        self._log_btn.setToolTip("Open the log file of the current or last run")
        self._log_btn.clicked.connect(self._show_log)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 8, 0)
        tab_row.setSpacing(8)
        tab_row.addWidget(tabbar)
        tab_row.addStretch(1)
        tab_row.addWidget(self._history_btn)
        tab_row.addWidget(self._log_btn)
        root.addLayout(tab_row)
        root.addWidget(stack, 1)
        self.setStyleSheet(f"""
            QPushButton#WizRunnerLogBtn {{
                background: {BG_INPUT}; color: {TEXT_DIM};
                border: 1px solid {BORDER}; border-radius: 6px;
                padding: 6px 12px; font-size: 12px;
            }}
            QPushButton#WizRunnerLogBtn:hover {{ color: {TEXT}; border: 1px solid {PURPLE_DIM}; }}
            QTabBar#WizRunnerTabBar {{ background: {PANEL}; }}
            QTabBar#WizRunnerTabBar::tab {{
                background: {PANEL}; color: {TERM_MUTE};
                padding: 10px 20px; margin: 0; border: none;
                border-right: 1px solid {BORDER_SOFT}; border-radius: 0;
            }}
            QTabBar#WizRunnerTabBar::tab:hover {{ color: {CONSOLE_TEXT}; }}
            QTabBar#WizRunnerTabBar::tab:selected {{
                background: {CONSOLE_BG}; color: {CONSOLE_TEXT};
                border-bottom: 3px solid {PURPLE};
            }}
        """)

        self._driver: WizardDriver | None = None
        self._start_btn = None
        self._stop_btn = None

    def bind_start_button(self, button) -> None:
        self._start_btn = button

    def bind_stop_button(self, button) -> None:
        self._stop_btn = button
        button.setEnabled(self._driver is not None)

    def stop(self) -> None:
        if self._driver is not None:
            self._stop_requested = True
            self._close_run(history_store.STOPPED)
            self._driver.stop()

    def is_running(self) -> bool:
        return self._driver is not None

    def current_log_path(self) -> Path | None:
        return self._log_path

    def history(self) -> ScanHistory:
        return self._history

    def start(self, data: dict) -> None:
        if self._driver is not None:
            return
        target = data.get("target", "").strip()
        if not target:
            return

        self.progress.clear()
        self.raw_output.clear()
        self._log_path = None
        self._stop_requested = False
        self._run = self._history.start(target)
        self._show(("Info", "-", "-", f"Starting wizard — target {target}", "-"))
        self._launch(WizardDriver(
            target=target,
            user_wordlist=data.get("user_wordlist", ""),
            pass_wordlist=data.get("pass_wordlist", ""),
            parent=self,
            checkpoint=_chain_relpath(self._history.checkpoint_path(self._run.id)),
        ))

    def resume(self, run_id: str) -> None:
        if self._driver is not None:
            return
        run = self._history.load(run_id)
        if run is None or not self._history.resumable(run):
            QMessageBox.information(
                self, "Resume scan",
                "This scan cannot be resumed. Only a scan that was stopped or interrupted "
                "after its scan step, and that has not finished, can be resumed.")
            return
        self._history.reopen(run)
        self._run = run
        self._stop_requested = False
        self._log_path = _chain_dir() / run.log_path if run.log_path else None
        self.progress.clear()
        self.raw_output.clear()
        for row in run.rows:
            self.progress.add_row(tuple(row))
        self._show(("Info", "-", "-",
                    "Resuming from checkpoint — steps that already finished are not run again", "-"))
        checkpoint = _chain_relpath(self._history.checkpoint_path(run.id))
        self._launch(WizardDriver(
            target=run.target,
            user_wordlist="",
            pass_wordlist="",
            parent=self,
            checkpoint=checkpoint,
            resume=checkpoint,
        ))

    def _launch(self, driver: WizardDriver) -> None:
        if self._start_btn:
            self._start_btn.setEnabled(False)
        if self._stop_btn:
            self._stop_btn.setEnabled(True)
        driver.menuRequested.connect(self._on_menu)
        driver.textRequested.connect(self._on_text)
        driver.multiselectRequested.connect(self._on_multiselect)
        driver.confirmRequested.connect(self._on_confirm)
        driver.sudoPasswordRequested.connect(self._on_sudo_password)
        driver.statusUpdate.connect(self._on_status)
        driver.rawOutput.connect(self.raw_output.append_chunk)
        driver.finished.connect(self._on_finished)
        driver.errorOccurred.connect(self._on_error)
        self._driver = driver
        driver.start()

    def _show(self, cells: tuple[str, ...]) -> None:
        self.progress.add_row(cells)
        if self._run is not None:
            self._history.add_row(self._run, cells)

    def _close_run(self, status: str, exit_code: int | None = None) -> None:
        if self._run is not None:
            self._history.finish(self._run, status, exit_code)
            self._run = None

    def _on_status(self, message: dict) -> None:
        kind = message.get("kind", "")
        if kind == "logfile":
            relative = message.get("data", {}).get("path", "")
            self._log_path = _chain_dir() / relative
            if self._run is not None:
                self._history.set_log_path(self._run, relative)
        elif kind == "shell_request":
            data = message.get("data", {}) or {}
            self._open_shell(data.get("cmd", ""), data.get("title", "TheRecon session"))
        self._show(status_row(message))

    def _on_menu(self, message: dict) -> None:
        reply = dialogs.show_menu_dialog(self, message)
        if self._driver:
            self._driver.respond({"reply": reply})

    def _on_text(self, message: dict) -> None:
        reply = dialogs.show_text_dialog(self, message)
        if self._driver:
            self._driver.respond({"reply": reply})

    def _on_multiselect(self, message: dict) -> None:
        reply = dialogs.show_multiselect_dialog(self, message)
        if self._driver:
            self._driver.respond({"reply": reply})

    def _on_confirm(self, message: dict) -> None:
        accepted = dialogs.show_confirm_dialog(self, message)
        if self._driver:
            self._driver.respond_confirm(accepted)

    def _on_sudo_password(self) -> None:
        password = dialogs.show_sudo_password_dialog(self)
        if self._driver:
            self._driver.respond({"reply": password})

    def _on_finished(self, exit_code: int) -> None:
        self._show(("Finished", "-", "-", f"exit code {exit_code}", "-"))
        status = history_store.STOPPED if self._stop_requested else history_store.FINISHED
        self._close_run(status, exit_code)
        self._release_driver()

    def _on_error(self, text: str) -> None:
        self._show(("Error", "-", "-", text, "Error"))
        self._close_run(history_store.FAILED)
        self._release_driver()

    def _release_driver(self) -> None:
        self._driver = None
        if self._start_btn:
            self._start_btn.setEnabled(True)
        if self._stop_btn:
            self._stop_btn.setEnabled(False)

    def _show_log(self) -> None:
        logs = find_logs(_chain_dir())
        if not logs:
            QMessageBox.information(
                self, "View log",
                "No log yet. A log file is created when a scan runs its first command.")
            return
        selected = next((p for p in logs if self._log_path and p.resolve() == self._log_path.resolve()), None)
        LogViewerDialog(logs, selected, self).exec()

    def _show_history(self) -> None:
        if self.is_running():
            QMessageBox.information(
                self, "Scan history",
                "A scan is running. Stop it first, then open the history.")
            return
        dialog = _HistoryDialog(self._history, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_id:
            return
        if dialog.selected_action == "resume":
            self.resume(dialog.selected_id)
            return
        run = self._history.load(dialog.selected_id)
        if run is None:
            return
        status = _STATUS_LABELS.get(run.status, run.status)
        self.progress.show_saved(
            run.rows,
            f"Saved run · {run.target} · started {run.started} · {status} · "
            f"{len(run.rows)} row(s) — read-only, nothing is run again")
        self.raw_output.clear()
        self.raw_output.append_chunk(_RAW_OUTPUT_NOTE + "\n")
        self._log_path = _chain_dir() / run.log_path if run.log_path else None

    def _open_shell(self, cmd: str, title: str) -> None:
        if not cmd:
            return
        script = (
            f"docker exec -it {_TOOL_CONTAINER} bash -lc {shlex.quote(cmd)}; "
            "echo; read -rp 'Session ended. Press Enter to close... ' _"
        )
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["wsl.exe", "-e", "bash", "-lc", script],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                return
            for term in (["x-terminal-emulator", "-e"], ["xterm", "-e"]):
                try:
                    subprocess.Popen([*term, "bash", "-lc", script])
                    return
                except FileNotFoundError:
                    continue
            raise FileNotFoundError("no terminal emulator found")
        except OSError:
            QMessageBox.warning(
                self, "Open session",
                f"Could not open a console window for: {title}\n\n"
                f"Run this yourself in a terminal:\n\ndocker exec -it "
                f"{_TOOL_CONTAINER} bash -lc {cmd}")
