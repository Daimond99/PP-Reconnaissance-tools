"""
Wizard control panel — the always-visible form on the left of the Wizard
Console. A beginner fills target / wordlists here and presses Start scan
instead of answering the chain CLI's raw text prompts one at a time. The
scan mode is always AUTO — the SEMI (pick-per-port) mode was removed
2026-08-29 as unused; there's nothing left to pick, so no mode control is
shown.

Save Profile / Load Profile round-trip target + both wordlist paths through
a JSON file the user picks — a pre-fill convenience only, no command/flags
baked in; loading one still requires pressing Start scan and answering
every per-step confirmation same as typing the fields in fresh.

The panel only *collects* choices and emits `scanRequested(dict)`; it never
builds or runs a command. `main_content.py` wires that signal to
`WizardRunner.start` (`src/ui/wizard_runner.py`), which launches the same
`chain_wizard` CLI (hidden, `--gui`, JSON protocol — no terminal) and answers
every menu/confirmation with a Qt dialog. The CLI still does its own
per-step confirmation once a scan starts, now routed through
`ConfirmationGate(channel="wizard")` — this form sits entirely ahead of that
gate, so no safety path is bypassed.

Styling reuses the app's own controls so the panel reads as part of the
mission bar: fields carry the `MissionInput` object name, which picks up the
global stylesheet — only panel-specific chrome is styled locally.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox,
)

from src.config import (
    BG_APP, PANEL, BG_INPUT, PURPLE, PURPLE_DIM, TEXT, TEXT_DIM,
    BORDER, ACCENT_RED,
)


class WizardControlPanel(QWidget):
    """Embedded scan form. Emits `scanRequested(dict)` on Start scan."""

    scanRequested = Signal(dict)
    stopRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("WizardPanel")
        self.setFixedWidth(280)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(9)

        heading = QLabel("New scan")
        heading.setObjectName("WizHeading")
        root.addWidget(heading)

        sub = QLabel(
            "1. Fill in the target below (wordlists are optional).\n"
            "2. Press Start scan.\n"
            "3. Pick a scan type, then confirm each step — every one shows up "
            "as a dialog beside this panel."
        )
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

        root.addSpacing(6)

        # Profile import/export — saves target + both wordlist paths as one
        # JSON file, so a repeat engagement against the same lab doesn't
        # mean re-typing/re-browsing everything. Deliberately just these
        # three fields (no command/flags baked in) — actually building and
        # running anything from a loaded profile still goes through Start
        # scan -> the normal scan-type menu -> ConfirmationGate, same as
        # typing it in fresh; a profile file can't skip that.
        profile_row = QHBoxLayout()
        profile_row.setContentsMargins(0, 0, 0, 0)
        profile_row.setSpacing(6)
        self.save_profile_btn = QPushButton("Save Profile…")
        self.save_profile_btn.setObjectName("WizBrowse")
        self.save_profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_profile_btn.clicked.connect(self._on_save_profile)
        profile_row.addWidget(self.save_profile_btn)
        self.load_profile_btn = QPushButton("Load Profile…")
        self.load_profile_btn.setObjectName("WizBrowse")
        self.load_profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_profile_btn.clicked.connect(self._on_load_profile)
        profile_row.addWidget(self.load_profile_btn)
        root.addLayout(profile_row)

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

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("WizStop")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stopRequested.emit)
        root.addWidget(self.stop_btn)

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

    def _on_save_profile(self) -> None:
        """Write target + both wordlist paths to a JSON file the user picks.
        Wordlists are saved as whatever path is currently in each field —
        if that's a Windows path, loading the profile back in still goes
        through the normal `_win_to_wsl_path` conversion at scan-launch
        time (`wizard/main.py::_parse_args`), same as typing it fresh."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save profile", "", "TheRecon profile (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        profile = {
            "target": self.target.text().strip(),
            "user_wordlist": self.user_wl.text().strip(),
            "pass_wordlist": self.pass_wl.text().strip(),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "Save Profile Failed", str(exc))

    def _on_load_profile(self) -> None:
        """Read a profile JSON back into the three fields — never touches
        `scanRequested` itself, so loading a profile only pre-fills the
        form; Start scan still has to be pressed and every step still
        needs its own confirmation, same as any other scan."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load profile", "", "TheRecon profile (*.json);;All files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Load Profile Failed", str(exc))
            return
        if not isinstance(profile, dict):
            QMessageBox.warning(self, "Load Profile Failed",
                                 "Not a valid TheRecon profile file.")
            return
        self.target.setText(str(profile.get("target", "")))
        self.user_wl.setText(str(profile.get("user_wordlist", "")))
        self.pass_wl.setText(str(profile.get("pass_wordlist", "")))

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
        QPushButton#WizStart:disabled {{
            background: {BG_INPUT}; border: 1px solid {BORDER}; color: {TEXT_DIM};
        }}
        QPushButton#WizStop {{
            background: {BG_INPUT}; border: 1px solid {ACCENT_RED};
            color: {ACCENT_RED}; font-size: 13px; font-weight: 600;
            border-radius: 8px; padding: 11px;
        }}
        QPushButton#WizStop:hover {{ background: {ACCENT_RED}; color: {BG_APP}; }}
        QPushButton#WizStop:disabled {{
            background: {BG_INPUT}; border: 1px solid {BORDER}; color: {TEXT_DIM};
        }}
        """
