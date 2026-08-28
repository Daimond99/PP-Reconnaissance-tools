"""
WizardRunner — connects `WizardControlPanel.scanRequested` to a
`WizardDriver` and answers its signals with the dialogs in
`wizard_dialogs.py`, so a wizard run is entirely Qt widgets end to end (no
terminal tab, no raw text typed anywhere). Two read-only views sit side by
side under a tab bar:
  - `WizardProgressView` — one table row per structured status event (scan
    result / step outcome / credential found / summary), same shape for
    every tool in the chain. Plain text only: no icons, no per-row color
    coding — a "Status" column carries the outcome as a word.
  - `WizardRawOutputView` — the wizard subprocess's actual captured command
    output (nmap/hydra/... stdout, echoed via `core.display`), which is
    real terminal-shaped content by nature (see `WizardDriver.rawOutput`),
    kept separate from the live-PTY `RawOutputTab` Direct Tool Mode owns —
    that widget executes typed keystrokes, so it cannot be reused as a
    passive log sink for another subprocess's output.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QPlainTextEdit, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from src.config import BG_INPUT, BORDER, PANEL, TERMINAL_FONT_FAMILY, TEXT, TEXT_DIM
from src.core.wizard_driver import WizardDriver
from src.ui import wizard_dialogs as dialogs

_COLUMNS = ["Type", "Target", "Tool", "Detail", "Status"]

# How each status `kind` maps onto the fixed 5-column row shape. `data` keys
# are read defensively (`.get`) since every producer already fills them, but
# a missing key should render "-" rather than crash the row.
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


class WizardProgressView(QWidget):
    """Table of structured status rows — the empty-state hint before the
    first scan, then one row per status update. Every tool in the chain
    (nmap/masscan/hydra/ncrack/ncat/evil-winrm) produces the same 5-column
    shape, so the table reads consistently regardless of which tool a row
    came from."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("WizProgress")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

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

    def _add_row(self, cells: tuple[str, ...]) -> None:
        self._stack.setCurrentWidget(self._table)
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, value in enumerate(cells):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, col, item)
        self._table.scrollToBottom()

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._stack.setCurrentWidget(self._empty)

    def append(self, text: str) -> None:
        self._add_row(("Info", "-", "-", text, "-"))

    def status(self, message: dict) -> None:
        kind = message.get("kind", "")
        builder = _ROW_BUILDERS.get(kind)
        data = message.get("data", {}) or {}
        text = message.get("text", "")
        cells = builder(data, text) if builder else ("Info", "-", "-", text, "-")
        self._add_row(cells)

    def finished(self, exit_code: int) -> None:
        self._add_row(("Finished", "-", "-", f"exit code {exit_code}", "-"))

    def error(self, text: str) -> None:
        self._add_row(("Error", "-", "-", text, "Error"))


class WizardRawOutputView(QWidget):
    """Read-only viewer for the wizard subprocess's real captured command
    output (nmap/hydra/... stdout as echoed by `core.display`) — genuine
    terminal-shaped content, unlike the ambient progress table, so a
    monospace font here is representing real output rather than decorating
    an otherwise-empty panel."""

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


class WizardRunner(QWidget):
    """Owns the progress/raw-output tabs + the currently running
    `WizardDriver` (if any). Wire `WizardControlPanel.scanRequested` to
    `start`."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.progress = WizardProgressView()
        self.raw_output = WizardRawOutputView()
        tabs = QTabWidget()
        tabs.addTab(self.progress, "Progress")
        tabs.addTab(self.raw_output, "Raw Output")
        root.addWidget(tabs)

        self._driver: WizardDriver | None = None
        self._start_btn = None  # set via bind_start_button
        self._stop_btn = None  # set via bind_stop_button

    def bind_start_button(self, button) -> None:
        """So the control panel's Start button disables while a run is in
        flight — prevents a second `WizardDriver`/subprocess stacking on
        top of one still running."""
        self._start_btn = button

    def bind_stop_button(self, button) -> None:
        """Enabled only while a run is in flight — the one place a user can
        kill a wizard run without closing the whole app."""
        self._stop_btn = button
        button.setEnabled(self._driver is not None)

    def stop(self) -> None:
        """Kill a run in flight — used both by the Stop button and on app
        shutdown. `WizardDriver.stop()` kills the QProcess; the resulting
        `finished` signal still fires, so `_on_finished` re-enables Start /
        disables Stop the same way a normal completion does."""
        if self._driver is not None:
            self._driver.stop()

    def start(self, data: dict) -> None:
        if self._driver is not None:
            return  # a run is already in flight
        target = data.get("target", "").strip()
        if not target:
            return

        self.progress.clear()
        self.raw_output.clear()
        self.progress.append(f"Starting wizard — target {target}, "
                              f"mode {data.get('mode', 'auto').upper()}")
        if self._start_btn:
            self._start_btn.setEnabled(False)
        if self._stop_btn:
            self._stop_btn.setEnabled(True)

        driver = WizardDriver(
            target=target,
            mode=data.get("mode", "auto"),
            user_wordlist=data.get("user_wordlist", ""),
            pass_wordlist=data.get("pass_wordlist", ""),
            parent=self,
        )
        driver.menuRequested.connect(self._on_menu)
        driver.textRequested.connect(self._on_text)
        driver.multiselectRequested.connect(self._on_multiselect)
        driver.confirmRequested.connect(self._on_confirm)
        driver.sudoPasswordRequested.connect(self._on_sudo_password)
        driver.statusUpdate.connect(self.progress.status)
        driver.rawOutput.connect(self.raw_output.append_chunk)
        driver.finished.connect(self._on_finished)
        driver.errorOccurred.connect(self._on_error)
        self._driver = driver
        driver.start()

    # -- driver signal handlers -------------------------------------------

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
        self.progress.finished(exit_code)
        self._driver = None
        if self._start_btn:
            self._start_btn.setEnabled(True)
        if self._stop_btn:
            self._stop_btn.setEnabled(False)

    def _on_error(self, text: str) -> None:
        self.progress.error(text)
        self._driver = None
        if self._start_btn:
            self._start_btn.setEnabled(True)
        if self._stop_btn:
            self._stop_btn.setEnabled(False)
