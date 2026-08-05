"""
Wizard control panel — the always-visible form on the left of the Wizard
Console. A beginner fills target / mode / wordlists here and presses Start
scan instead of answering the chain CLI's raw text prompts one at a time.

The panel only *collects* choices and emits `scanRequested(dict)`; it never
builds or runs a command. The container wires that signal to
`TerminalTabsWidget.start_wizard_scan`, which launches the same
`chain_wizard` CLI with those choices as flags. The CLI still does its own
per-step confirmation once a scan starts — this form sits entirely ahead of
that gate, so no safety path is bypassed.

Styling reuses the app's own controls so the panel reads as part of the
mission bar: fields carry the `MissionInput` object name and the mode picker
is the same `DropdownButton` (▾) the TOOLS/WARHEAD combos use, both of which
pick up the global stylesheet — only panel-specific chrome is styled locally.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog,
)

from src.config import (
    BG_APP, PANEL, BG_INPUT, PURPLE, PURPLE_DIM, TEXT, TEXT_DIM,
    BORDER, ACCENT_RED,
)


class WizardControlPanel(QWidget):
    """Embedded scan form. Emits `scanRequested(dict)` on Start scan."""

    scanRequested = Signal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("WizardPanel")
        self.setFixedWidth(280)

        # Lazy import: widgets.py imports this module at load time, so a
        # top-level `from src.ui.widgets import DropdownButton` would be a
        # circular import. By construction time widgets is fully loaded.
        from src.ui.widgets import DropdownButton

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(9)

        heading = QLabel("New scan")
        heading.setObjectName("WizHeading")
        root.addWidget(heading)

        sub = QLabel("Fill these in, then press Start — the wizard runs in the terminal beside this.")
        sub.setObjectName("WizSub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        root.addSpacing(6)

        # Target
        root.addWidget(self._field_label("Target"))
        self.target = QLineEdit()
        self.target.setObjectName("MissionInput")
        self.target.setPlaceholderText("192.168.1.100")
        self.target.returnPressed.connect(self._on_start)
        root.addWidget(self.target)

        root.addSpacing(2)

        # Mode — same DropdownButton (▾) as the mission-bar combos.
        root.addWidget(self._field_label("Scan mode"))
        self.mode = DropdownButton(["AUTO — auto-pick per port",
                                    "SEMI — pick per port"])
        self.mode.setObjectName("MissionCombo")
        root.addWidget(self.mode)

        root.addSpacing(2)

        # User wordlist
        root.addWidget(self._field_label("User wordlist"))
        self.user_wl = QLineEdit()
        self.user_wl.setObjectName("MissionInput")
        self.user_wl.setPlaceholderText("blank = rockyou.txt")
        root.addLayout(self._browse_row(self.user_wl))

        root.addSpacing(2)

        # Pass wordlist
        root.addWidget(self._field_label("Pass wordlist"))
        self.pass_wl = QLineEdit()
        self.pass_wl.setObjectName("MissionInput")
        self.pass_wl.setPlaceholderText("blank = same as user")
        root.addLayout(self._browse_row(self.pass_wl))

        root.addStretch(1)

        self.hint = QLabel("")
        self.hint.setObjectName("WizHint")
        self.hint.setWordWrap(True)
        self.hint.setVisible(False)
        root.addWidget(self.hint)

        self.start_btn = QPushButton("Start scan")
        self.start_btn.setObjectName("WizStart")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)
        root.addWidget(self.start_btn)

        self.target.setFocus()
        self.setStyleSheet(self._qss())

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _field_label(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("WizFieldLabel")
        return lab

    def _browse_row(self, edit: QLineEdit) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(edit, 1)
        browse = QPushButton("Browse")
        browse.setObjectName("WizBrowse")
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.setToolTip("Browse for a wordlist file")
        browse.clicked.connect(lambda: self._browse_into(edit))
        h.addWidget(browse)
        return h

    def _browse_into(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select wordlist", "", "Wordlists (*.txt *.lst);;All files (*)")
        if path:
            edit.setText(path)

    def _current_mode(self) -> str:
        return "auto" if self.mode.currentText().startswith("AUTO") else "semi"

    def _on_start(self) -> None:
        target = self.target.text().strip()
        if not target:
            self.hint.setText("Enter a target first.")
            self.hint.setVisible(True)
            self.target.setFocus()
            return
        self.hint.setVisible(False)
        self.scanRequested.emit({
            "target": target,
            "mode": self._current_mode(),
            "user_wordlist": self.user_wl.text().strip(),
            "pass_wordlist": self.pass_wl.text().strip(),
        })

    # -- style ------------------------------------------------------------
    def _qss(self) -> str:
        # Fields (MissionInput) and the mode picker (MissionCombo) inherit the
        # global app stylesheet — only panel-specific chrome is styled here.
        return f"""
        QWidget#WizardPanel {{
            background: {PANEL};
            border-right: 1px solid {BORDER};
        }}
        QLabel#WizHeading {{ color: {TEXT}; font-size: 16px; font-weight: 600; }}
        QLabel#WizSub {{ color: {TEXT_DIM}; font-size: 11px; line-height: 16px; }}
        QLabel#WizFieldLabel {{
            color: {TEXT_DIM}; font-size: 11px; font-weight: 500;
            text-transform: uppercase; letter-spacing: 1px;
        }}
        QLabel#WizHint {{ color: {ACCENT_RED}; font-size: 11px; }}
        QPushButton#WizBrowse {{
            background: {BG_INPUT}; color: {TEXT_DIM};
            border: 1px solid {BORDER}; border-radius: 7px;
            padding: 8px 12px; font-size: 12px;
        }}
        QPushButton#WizBrowse:hover {{ color: {TEXT}; border: 1px solid {PURPLE_DIM}; }}
        QPushButton#WizStart {{
            background: {PURPLE_DIM}; border: 1px solid {PURPLE};
            color: {TEXT}; font-size: 13px; font-weight: 600;
            border-radius: 8px; padding: 11px;
        }}
        QPushButton#WizStart:hover {{ background: {PURPLE}; color: {BG_APP}; }}
        """
