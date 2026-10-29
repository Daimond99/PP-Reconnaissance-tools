from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from src.config import (
    ACCENT_GREEN, ACCENT_RED, BG_INPUT, BORDER, PANEL, PURPLE, PURPLE_DIM,
    TERMINAL_FONT_FAMILY, TEXT, TEXT_DIM, TEXT_MUTE, TOOL_COMMANDS,
)
from src.core.warhead_store import validate_profile

_QSS = f"""
    QDialog {{ background: {PANEL}; }}
    QLabel {{ color: {TEXT_DIM}; font-size: 12px; background: transparent; }}
    QLabel#WarheadSection {{ color: {TEXT_MUTE}; font-size: 10px; }}
    QLabel#WarheadHelp {{ color: {TEXT_MUTE}; font-size: 11px; }}
    QLineEdit, QComboBox {{
        background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
        border-radius: 6px; padding: 8px 10px; selection-background-color: {PURPLE_DIM};
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {PURPLE}; }}
    QComboBox QAbstractItemView, QListWidget {{
        background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
        border-radius: 6px; padding: 4px; selection-background-color: {PURPLE_DIM};
    }}
    QListWidget::item {{ padding: 8px 10px; border-radius: 4px; }}
    QListWidget::item:selected {{ background: {PURPLE_DIM}; color: {TEXT}; }}
    QPushButton {{
        background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
        border-radius: 6px; padding: 8px 16px;
    }}
    QPushButton:hover {{ border: 1px solid {PURPLE_DIM}; }}
    QPushButton:disabled {{ color: {TEXT_MUTE}; }}
"""


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("WarheadSection")
    return label


class AddWarheadDialog(QDialog):
    def __init__(self, tools: list[str], default_tool: str, taken: set[str],
                 parent: QWidget | None = None,
                 initial: tuple[str, str, str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit warhead profile" if initial else "New warhead profile")
        self.setMinimumWidth(680)
        self.setStyleSheet(_QSS)
        self._taken = set(taken)
        self._command_edited = initial is not None
        self._prefilling = False

        self._tool = QComboBox()
        self._tool.addItems(tools)
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Nmap - Quiet weekend sweep")
        self._name.setMaxLength(60)
        self._command = QLineEdit()
        self._command.setFont(QFont(TERMINAL_FONT_FAMILY))
        self._command.setPlaceholderText("sudo nmap -sS -T2 192.168.1.0/24")

        if initial is not None:
            tool, name, command = initial
            self._tool.setCurrentText(tool if tool in tools else default_tool)
            self._name.setText(name)
            self._command.setText(command)
        elif default_tool in tools:
            self._tool.setCurrentText(default_tool)

        self._hint = QLabel()
        self._hint.setWordWrap(True)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Save changes" if initial else "Save profile")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        help_text = QLabel(
            "The command is a template. 192.168.1.1 or 192.168.1.0/24 stands in for the "
            "target, which is filled in from the TARGET field when the profile is picked. "
            "Running it still goes through the confirmation step.")
        help_text.setWordWrap(True)
        help_text.setObjectName("WarheadHelp")

        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.addWidget(_section("TOOL"))
        root.addWidget(self._tool)
        root.addWidget(_section("NAME"))
        root.addWidget(self._name)
        root.addWidget(_section("COMMAND"))
        root.addWidget(self._command)
        root.addWidget(help_text)
        root.addSpacing(4)
        root.addWidget(self._hint)
        root.addSpacing(8)
        root.addWidget(self._buttons)

        self._tool.currentTextChanged.connect(self._on_tool_changed)
        self._name.textChanged.connect(lambda _t: self._validate())
        self._command.textChanged.connect(self._on_command_changed)
        self._on_tool_changed(self._tool.currentText())

    @property
    def tool(self) -> str:
        return self._tool.currentText()

    @property
    def name(self) -> str:
        return self._name.text().strip()

    @property
    def command(self) -> str:
        return self._command.text().strip()

    def _on_command_changed(self, _text: str) -> None:
        if not self._prefilling:
            self._command_edited = True
        self._validate()

    def _on_tool_changed(self, tool: str) -> None:
        if not self._command_edited:
            self._prefilling = True
            try:
                self._command.setText(TOOL_COMMANDS.get(tool, ""))
            finally:
                self._prefilling = False
        self._validate()

    def _validate(self) -> None:
        errors = validate_profile(self.tool, self.name, self.command, self._taken)
        save = self._buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setEnabled(not errors)
        if errors:
            self._hint.setText("\n".join(f"• {error}" for error in errors))
            self._hint.setStyleSheet(f"color: {ACCENT_RED};")
        else:
            self._hint.setText("Ready to save.")
            self._hint.setStyleSheet(f"color: {ACCENT_GREEN};")


class ManageWarheadDialog(QDialog):
    def __init__(self, custom: dict[str, dict[str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Your warhead profiles")
        self.setMinimumWidth(640)
        self.setStyleSheet(_QSS)
        self.action: str | None = None
        self.tool = ""
        self.name = ""
        self._entries: list[tuple[str, str, str]] = []

        self._list = QListWidget()
        for tool, profiles in custom.items():
            for name, command in profiles.items():
                self._entries.append((tool, name, command))
                item = QListWidgetItem(f"{tool}   ·   {name}")
                item.setData(Qt.ItemDataRole.UserRole, len(self._entries) - 1)
                item.setToolTip(command)
                self._list.addItem(item)
        self._list.currentRowChanged.connect(lambda _row: self._refresh())
        self._list.itemDoubleClicked.connect(lambda _item: self._choose("edit"))

        self._empty = QLabel("You have no profiles of your own yet. Use + next to the "
                             "WARHEAD PROFILE box to add one.")
        self._empty.setWordWrap(True)
        self._empty.setVisible(not self._entries)

        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.clicked.connect(lambda: self._choose("edit"))
        self._delete_btn = QPushButton("Delete…")
        self._delete_btn.clicked.connect(lambda: self._choose("delete"))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._edit_btn)
        row.addWidget(self._delete_btn)
        row.addStretch(1)
        row.addWidget(close_btn)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addWidget(_section("ONLY PROFILES YOU ADDED ARE LISTED — BUILT-IN ONES STAY FIXED"))
        root.addWidget(self._list, 1)
        root.addWidget(self._empty)
        root.addLayout(row)
        self._refresh()

    def _refresh(self) -> None:
        has_selection = self._list.currentRow() >= 0
        self._edit_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)

    def _choose(self, action: str) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        tool, name, _command = self._entries[item.data(Qt.ItemDataRole.UserRole)]
        self.action, self.tool, self.name = action, tool, name
        self.accept()
