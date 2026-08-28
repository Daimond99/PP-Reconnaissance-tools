"""
Qt dialogs that answer `WizardDriver`'s signals — the GUI replacement for
every text menu/confirmation `chain_wizard`'s CLI used to print. Each
dialog only *renders* data the driver already carries (built entirely in
`chain_wizard/`, see CLAUDE.md's "GUI never builds commands or holds
security logic") and returns a choice/boolean; none of them construct a
command string.

Kept as plain functions returning `QDialog.exec()` results rather than
persistent widgets — a wizard run pops these one at a time, synchronously,
same shape as the old blocking `input()` calls they replace.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QTextEdit, QLineEdit, QDialogButtonBox,
)

from src.config import (
    BG_APP, PANEL, BG_INPUT, PURPLE, PURPLE_DIM, TEXT, TEXT_DIM,
    BORDER, ACCENT_RED, ACCENT_GREEN,
)

_DIALOG_QSS = f"""
QDialog {{ background: {PANEL}; }}
QLabel {{ color: {TEXT}; }}
QLabel#WizDialogTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#WizDialogHint {{ color: {TEXT_DIM}; font-size: 11px; }}
QListWidget {{
    background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 4px;
}}
QTextEdit {{
    background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 8px; font-family: Consolas, monospace;
}}
QLineEdit {{
    background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 6px;
}}
QPushButton {{
    background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 8px 16px;
}}
QPushButton:hover {{ border: 1px solid {PURPLE_DIM}; }}
QPushButton#WizRun {{ background: {PURPLE_DIM}; border: 1px solid {PURPLE}; }}
QPushButton#WizRun:hover {{ background: {PURPLE}; color: {BG_APP}; }}
"""

_PRIORITY_LABEL = {5: "RCE / shell", 4: "recommended", 3: "optional", 2: "info"}
_PRIORITY_COLOR = {5: ACCENT_RED, 4: ACCENT_GREEN, 3: TEXT_DIM, 2: TEXT_DIM}


def _base_dialog(parent, title: str) -> QDialog:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(480)
    dlg.setStyleSheet(_DIALOG_QSS)
    return dlg


def show_menu_dialog(parent, message: dict) -> str:
    """Single-choice numbered menu (scanner type, mode, masscan profile...).
    Returns the leading digit/letter of the chosen option (e.g. "1", "7")."""
    dlg = _base_dialog(parent, message.get("title", "Choose"))
    root = QVBoxLayout(dlg)
    title = QLabel(message.get("title", ""))
    title.setObjectName("WizDialogTitle")
    title.setWordWrap(True)
    root.addWidget(title)

    lst = QListWidget()
    lst.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    options = message.get("options", [])
    default = message.get("default", "")
    default_row = 0
    for i, opt in enumerate(options):
        item = QListWidgetItem(opt)
        lst.addItem(item)
        if opt.strip().startswith(f"{default}."):
            default_row = i
    if options:
        lst.setCurrentRow(default_row)
    lst.itemDoubleClicked.connect(lambda _i: dlg.accept())
    root.addWidget(lst)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    root.addWidget(buttons)

    if dlg.exec() != QDialog.DialogCode.Accepted or lst.currentRow() < 0:
        return default
    chosen = options[lst.currentRow()]
    return chosen.split(".", 1)[0].strip()


def show_text_dialog(parent, message: dict) -> str:
    """Free-text prompt (target, wordlist path, timing/rate values)."""
    dlg = _base_dialog(parent, message.get("prompt", "Enter value"))
    root = QVBoxLayout(dlg)
    title = QLabel(message.get("prompt", ""))
    title.setObjectName("WizDialogTitle")
    title.setWordWrap(True)
    root.addWidget(title)

    edit = QLineEdit()
    default = message.get("default", "")
    edit.setText(default)
    edit.setPlaceholderText(default)
    edit.selectAll()
    root.addWidget(edit)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    edit.returnPressed.connect(dlg.accept)
    root.addWidget(buttons)
    edit.setFocus()

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return default
    return edit.text().strip() or default


def show_multiselect_dialog(parent, message: dict) -> str:
    """Checkable list of steps/ports. Returns the raw picks string the
    original CLI parsers already understand ("1,3", "r", "a", "0")."""
    dlg = _base_dialog(parent, message.get("title", "Select steps"))
    root = QVBoxLayout(dlg)
    title = QLabel(message.get("title", ""))
    title.setObjectName("WizDialogTitle")
    title.setWordWrap(True)
    root.addWidget(title)

    items = message.get("items", [])
    lst = QListWidget()
    has_priority = any("priority" in item for item in items)
    for item in items:
        port, service = item.get("port"), item.get("service")
        tool, name = item.get("tool", ""), item.get("name", "")
        if port is not None:
            prio = item.get("priority", 3)
            label = f"{port}/{service}  [{tool}] {name}  — {_PRIORITY_LABEL.get(prio, '')}"
        else:
            tag = "recommended" if item.get("is_recommended") else "alternative"
            label = f"[{tool}] {name}  — {tag}"
        li = QListWidgetItem(label)
        li.setFlags(li.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        li.setCheckState(Qt.CheckState.Unchecked)
        lst.addItem(li)
    root.addWidget(lst)

    if has_priority:
        hint = QLabel("Recommended = leads to creds / shell.")
        hint.setObjectName("WizDialogHint")
        root.addWidget(hint)

    btn_row = QHBoxLayout()
    if has_priority:
        rec_btn = QPushButton("Select recommended")
        rec_btn.clicked.connect(lambda: _check_all(lst, items, "priority", 4))
        btn_row.addWidget(rec_btn)
    all_btn = QPushButton("Select all")
    all_btn.clicked.connect(lambda: _set_all_checked(lst, True))
    btn_row.addWidget(all_btn)
    none_btn = QPushButton("Select none")
    none_btn.clicked.connect(lambda: _set_all_checked(lst, False))
    btn_row.addWidget(none_btn)
    root.addLayout(btn_row)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    root.addWidget(buttons)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return "0"
    picks = [str(i + 1) for i in range(lst.count())
             if lst.item(i).checkState() == Qt.CheckState.Checked]
    return ",".join(picks) if picks else "0"


def _set_all_checked(lst: QListWidget, checked: bool) -> None:
    state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
    for i in range(lst.count()):
        lst.item(i).setCheckState(state)


def _check_all(lst: QListWidget, items: list[dict], key: str, min_value) -> None:
    for i, item in enumerate(items):
        state = (Qt.CheckState.Checked if item.get(key, 0) >= min_value
                  else Qt.CheckState.Unchecked)
        lst.item(i).setCheckState(state)


def show_confirm_dialog(parent, message: dict) -> bool:
    """The safety-critical impact confirmation. `message["preview_box"]`
    was already built by `ConfirmationGate.request()` (same rendering as
    Direct Tool Mode's confirm box); if `message["allowed"]` is False the
    driver rejected the command before it ever reached this dialog — show
    the reason and offer only Cancel."""
    dlg = _base_dialog(parent, message.get("title", "Confirm"))
    root = QVBoxLayout(dlg)
    title = QLabel(message.get("title", ""))
    title.setObjectName("WizDialogTitle")
    title.setWordWrap(True)
    root.addWidget(title)

    box = QTextEdit()
    box.setReadOnly(True)
    allowed = message.get("allowed", True)
    if allowed:
        box.setPlainText(message.get("preview_box") or message.get("impact", ""))
    else:
        box.setPlainText(message.get("reject_reason") or "Command rejected.")
    box.setMinimumHeight(160)
    root.addWidget(box)

    buttons = QDialogButtonBox()
    if allowed:
        run_btn = buttons.addButton("Run", QDialogButtonBox.ButtonRole.AcceptRole)
        run_btn.setObjectName("WizRun")
        skip_btn = buttons.addButton("Skip", QDialogButtonBox.ButtonRole.RejectRole)
    else:
        skip_btn = buttons.addButton("OK", QDialogButtonBox.ButtonRole.RejectRole)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    root.addWidget(buttons)

    return allowed and dlg.exec() == QDialog.DialogCode.Accepted


def show_sudo_password_dialog(parent) -> str:
    """Masked password prompt — shown at most once per wizard run, the
    first time a sudo-prefixed command (masscan/nmap raw-socket flags)
    needs root inside WSL."""
    dlg = _base_dialog(parent, "sudo password")
    root = QVBoxLayout(dlg)
    label = QLabel("A scan step needs root (sudo) inside WSL.\nEnter your WSL sudo password:")
    label.setObjectName("WizDialogTitle")
    label.setWordWrap(True)
    root.addWidget(label)

    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    root.addWidget(edit)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    edit.returnPressed.connect(dlg.accept)
    root.addWidget(buttons)
    edit.setFocus()

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return ""
    return edit.text()
