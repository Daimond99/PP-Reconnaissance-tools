"""
LLM Nmap panel — the control panel on the LLM Mode page, between the raw
"OpenCode" and "LLM Nmap" shell terminals (`main_content.py`'s
`self.opencode_tab`/`self.llm_tab`), which stay untouched: those are plain,
ungated PTY shells by design (see docs/CURRENT_STATE.md). This panel is the
gated path — it only
*suggests* a command via `src.core.llm_nmap_suggest.suggest_nmap_command()`,
never runs anything itself. `executeRequested` is the sole way this widget
reaches outside itself; the container wires it to a handler that runs the
suggested (and user-editable) command through the same `ConfirmationGate`
Direct Tool Mode uses (validate -> preview -> exact "yes" -> execute) — no
shortcut path, per CLAUDE.md's AI rule.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
)

from src.config import (
    BG_APP, PANEL, BG_INPUT, PURPLE, PURPLE_DIM, TEXT, TEXT_DIM,
    BORDER, ACCENT_RED,
)
from src.core.llm_nmap_suggest import suggest_nmap_command


class _SuggestWorker(QThread):
    """Runs `suggest_nmap_command()` (a blocking subprocess call, up to
    `_TIMEOUT`s) off the Qt main thread — calling it directly from a button
    handler freezes the whole GUI for that long, which is what looked like
    a hang."""

    done = Signal(bool, str)

    def __init__(self, goal: str, target: str, parent=None):
        super().__init__(parent)
        self._goal = goal
        self._target = target

    def run(self) -> None:
        ok, text = suggest_nmap_command(self._goal, self._target)
        self.done.emit(ok, text)


class LlmNmapPanel(QWidget):
    """Target + goal -> AI-suggested (editable) nmap command -> gated
    execution request. Emits `executeRequested(command, target)`."""

    executeRequested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("LlmNmapPanel")
        self.setFixedWidth(300)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(9)

        heading = QLabel("LLM Nmap (gated)")
        heading.setObjectName("LlmHeading")
        root.addWidget(heading)

        sub = QLabel(
            "Picks from the same basic scan types the llm-tools-nmap "
            "plugin supports (quick/port/service/OS/ping/script scan). "
            "Review/edit the result, then request execution — it still "
            "goes through the same confirmation gate as Direct Tool Mode, "
            "runs right here on this page. (The raw OpenCode/LLM Nmap "
            "shells on either side are separate and unaffected.)"
        )
        sub.setObjectName("LlmSub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        root.addSpacing(6)

        root.addWidget(self._field_label("Target"))
        self.target = QLineEdit()
        self.target.setObjectName("MissionInput")
        self.target.setPlaceholderText("192.168.1.100")
        root.addWidget(self.target)

        root.addSpacing(2)

        root.addWidget(self._field_label("Goal"))
        self.goal = QLineEdit()
        self.goal.setObjectName("MissionInput")
        self.goal.setPlaceholderText("e.g. find open ports and service versions")
        root.addWidget(self.goal)

        root.addSpacing(6)

        self.suggest_btn = QPushButton("Suggest command")
        self.suggest_btn.setObjectName("LlmSuggest")
        self.suggest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.suggest_btn.clicked.connect(self._on_suggest)
        root.addWidget(self.suggest_btn)

        root.addSpacing(6)

        root.addWidget(self._field_label("Suggested command (editable)"))
        self.command = QLineEdit()
        self.command.setObjectName("MissionInput")
        self.command.setPlaceholderText("nothing suggested yet")
        root.addWidget(self.command)

        root.addStretch(1)

        self.hint = QLabel("")
        self.hint.setObjectName("LlmHint")
        self.hint.setWordWrap(True)
        self.hint.setVisible(False)
        root.addWidget(self.hint)

        self.execute_btn = QPushButton("Request execution")
        self.execute_btn.setObjectName("LlmExecute")
        self.execute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.execute_btn.clicked.connect(self._on_execute)
        root.addWidget(self.execute_btn)

        self.target.setFocus()
        self.setStyleSheet(self._qss())

        self._worker: _SuggestWorker | None = None

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _field_label(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("LlmFieldLabel")
        return lab

    def _show_hint(self, text: str) -> None:
        self.hint.setText(text)
        self.hint.setVisible(True)

    def _on_suggest(self) -> None:
        goal = self.goal.text().strip()
        target = self.target.text().strip()
        if not target:
            self._show_hint("Enter a target first.")
            self.target.setFocus()
            return
        if not goal:
            self._show_hint("Enter a goal first.")
            self.goal.setFocus()
            return
        if self._worker is not None:
            return  # a request is already in flight

        self.hint.setVisible(False)
        self.suggest_btn.setEnabled(False)
        self.suggest_btn.setText("Asking...")

        self._worker = _SuggestWorker(goal, target, self)
        self._worker.done.connect(self._on_suggest_done)
        self._worker.start()

    def _on_suggest_done(self, ok: bool, text: str) -> None:
        self.suggest_btn.setEnabled(True)
        self.suggest_btn.setText("Suggest command")
        self._worker = None

        if not ok:
            self._show_hint(f"[!] {text}")
            return
        self.command.setText(text)

    def _on_execute(self) -> None:
        cmd = self.command.text().strip()
        target = self.target.text().strip()
        if not cmd:
            self._show_hint("No command to run yet — suggest or type one first.")
            return
        if not target:
            self._show_hint("Enter a target first.")
            self.target.setFocus()
            return
        self.hint.setVisible(False)
        self.executeRequested.emit(cmd, target)

    # -- style ------------------------------------------------------------
    def _qss(self) -> str:
        return f"""
        QWidget#LlmNmapPanel {{
            background: {PANEL};
            border-right: 1px solid {BORDER};
        }}
        QLabel#LlmHeading {{ color: {TEXT}; font-size: 16px; font-weight: 600; }}
        QLabel#LlmSub {{ color: {TEXT_DIM}; font-size: 11px; line-height: 16px; }}
        QLabel#LlmFieldLabel {{
            color: {TEXT_DIM}; font-size: 11px; font-weight: 500;
            text-transform: uppercase; letter-spacing: 1px;
        }}
        QLabel#LlmHint {{ color: {ACCENT_RED}; font-size: 11px; }}
        QPushButton#LlmSuggest {{
            background: {BG_INPUT}; color: {TEXT};
            border: 1px solid {BORDER}; border-radius: 8px;
            padding: 9px; font-size: 12px; font-weight: 600;
        }}
        QPushButton#LlmSuggest:hover {{ border: 1px solid {PURPLE_DIM}; }}
        QPushButton#LlmExecute {{
            background: {PURPLE_DIM}; border: 1px solid {PURPLE};
            color: {TEXT}; font-size: 13px; font-weight: 600;
            border-radius: 8px; padding: 11px;
        }}
        QPushButton#LlmExecute:hover {{ background: {PURPLE}; color: {BG_APP}; }}
        """
