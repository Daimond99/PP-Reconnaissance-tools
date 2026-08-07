"""DropdownButton — a QComboBox-compatible dropdown backed by QPushButton +
QMenu (see the class docstring for why the native combo popup is avoided under
this app's frameless window)."""

from PySide6.QtWidgets import QPushButton, QLabel, QMenu, QHBoxLayout
from PySide6.QtCore import Signal, Qt

from src.config import TEXT


class DropdownButton(QPushButton):
    """Drop-in QComboBox replacement (`addItems`/`clear`/`currentText`/
    `blockSignals`/`currentTextChanged` — same surface main_window.py
    already calls) backed by a QPushButton + QMenu instead of Qt's native
    combo-box popup. Same technique the title-bar Settings button already
    uses (`main_window._on_settings_clicked`: `menu.exec(btn.mapToGlobal(...))`),
    which positions correctly under this app's frameless window — the
    native QComboBox popup's own position/geometry math doesn't account for
    that frameless window's offset the same way, which is what made the
    TOOLS/WARHEAD PROFILE dropdowns render misaligned and shift after a
    selection while Settings never had that problem."""

    currentTextChanged = Signal(str)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self._items: list[str] = []
        self._current = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Two overlay labels instead of a single setText() string: the old
        # "label + spaces + ▾" text let the arrow drift left/right with
        # every label's width (short "Nmap" vs long "Evil-WinRM"), so it
        # never lined up at the same spot across tools. Pinning the arrow
        # to its own fixed-width, right-anchored label keeps it at a
        # constant x regardless of the current label's length. Both labels
        # are click-through (WA_TransparentForMouseEvents) so the press
        # still reaches this QPushButton underneath.
        # Margins mirror the #MissionCombo stylesheet padding (8px vert,
        # 10px horiz) so the label text starts at the same left inset as the
        # sibling QLineEdit (TARGET). A layout on a QPushButton overrides the
        # stylesheet padding for child positioning, so with the old (0,0,0,0)
        # the label sat flush against the left border while the QLineEdit's
        # text kept its 10px pad -- that mismatch is what made the row look
        # unaligned even though every box is the same height.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 10, 8)
        layout.setSpacing(4)
        self._label = QLabel()
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._label.setStyleSheet(f"background: transparent; border: none; color: {TEXT};")
        self._arrow = QLabel("▾")
        self._arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._arrow.setStyleSheet(f"background: transparent; border: none; color: {TEXT};")
        self._arrow.setFixedWidth(14)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._arrow, 0)

        if items:
            self.addItems(items)
        self.clicked.connect(self._open_menu)

    def addItems(self, items) -> None:
        self._items.extend(items)
        if not self._current and self._items:
            self._current = self._items[0]
        self._refresh_text()

    def clear(self) -> None:
        self._items = []
        self._current = ""
        self._refresh_text()

    def currentText(self) -> str:
        return self._current

    def _refresh_text(self) -> None:
        self._label.setText(self._current)

    def _open_menu(self) -> None:
        if not self._items:
            return
        menu = QMenu(self)
        for label in self._items:
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, l=label: self._select(l))
        menu.setMinimumWidth(self.width())
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _select(self, label: str) -> None:
        if label == self._current:
            return
        self._current = label
        self._refresh_text()
        self.currentTextChanged.emit(label)
