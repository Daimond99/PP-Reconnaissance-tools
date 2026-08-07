"""InputManagementTab — the Zenmap-style scan queue. Every Direct Tool Mode
Execute lands a row here; Append/Remove/Cancel act on rows; a saved nmap XML
round-trips through here."""

import xml.etree.ElementTree as ET
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Signal, Qt

from src.config import (
    PURPLE, TEXT, TEXT_DIM, BORDER, BG_PANEL_2, TEXT_MUTE, ORANGE, ACCENT_GREEN,
)


class InputManagementTab(QWidget):
    """Zenmap-style scan queue. Every Direct Tool Mode Execute (top-bar)
    lands a row here (Status/Command); Append Scan loads a previously-saved
    nmap XML (-oX) back in as a reusable row, Remove Scan drops a row,
    Cancel Scan interrupts the selected (running) one. Double-click a row
    to put its command back into the top-bar command box."""

    reuseRequested = Signal(str)
    cancelRequested = Signal(int)

    STATUS_COLOR = {
        "Queued": TEXT_MUTE, "Running": ORANGE, "Done": ACCENT_GREEN,
        "Error": "#ff5555", "Cancelled": TEXT_MUTE, "Loaded": PURPLE,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Status", "Command"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {BG_PANEL_2}; color: {TEXT_DIM};
                border: 1px solid {BORDER}; border-radius: 8px;
                gridline-color: {BORDER};
            }}
            QHeaderView::section {{
                background-color: {BG_PANEL_2}; color: {TEXT_MUTE};
                border: none; border-bottom: 1px solid {BORDER};
                padding: 8px; font-size: 10.5px; font-weight: 700;
            }}
            QTableWidget::item:selected {{
                background-color: {PURPLE}; color: {TEXT};
            }}
        """)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table, 1)

        toolbar = QHBoxLayout()
        self.append_btn = QPushButton("+ Append Scan")
        self.append_btn.setObjectName("ActionButton")
        self.append_btn.clicked.connect(self._append_scan)
        self.remove_btn = QPushButton("− Remove Scan")
        self.remove_btn.setObjectName("ActionButton")
        self.remove_btn.clicked.connect(self._remove_scan)
        self.cancel_btn = QPushButton("✕ Cancel Scan")
        self.cancel_btn.setObjectName("ActionButton")
        self.cancel_btn.clicked.connect(self._cancel_scan)
        toolbar.addWidget(self.append_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addWidget(self.cancel_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

    # -- rows fed by the top-bar Direct Tool Mode Execute flow -------------
    def add_entry(self, command: str, status: str = "Queued", xml_path: str = "") -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._set_status_item(row, status)
        cmd_item = QTableWidgetItem(command)
        if xml_path:
            cmd_item.setData(Qt.ItemDataRole.UserRole, xml_path)
        self.table.setItem(row, 1, cmd_item)
        self.table.scrollToBottom()
        return row

    def set_status(self, row: int, status: str) -> None:
        if 0 <= row < self.table.rowCount():
            self._set_status_item(row, status)

    def _set_status_item(self, row: int, status: str) -> None:
        item = QTableWidgetItem(status)
        item.setForeground(QColor(self.STATUS_COLOR.get(status, TEXT_DIM)))
        self.table.setItem(row, 0, item)

    # -- toolbar actions -----------------------------------------------
    def _append_scan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Append Saved Scan", "", "Nmap XML (*.xml)"
        )
        if not path:
            return
        command = self._parse_nmap_xml_command(path)
        if not command:
            QMessageBox.warning(
                self, "Append Scan", "Could not read a command from that XML file."
            )
            return
        self.add_entry(command, status="Loaded", xml_path=path)

    @staticmethod
    def _parse_nmap_xml_command(path: str) -> Optional[str]:
        try:
            root = ET.parse(path).getroot()
        except Exception:
            return None
        if root.tag != "nmaprun":
            return None
        return root.get("args")

    @staticmethod
    def build_scan_xml(command: str) -> str:
        """Serialize a scan (its command) to a minimal nmap-run XML, so
        Open Scan can read the command back via _parse_nmap_xml_command."""
        root = ET.Element("nmaprun", {"scanner": "nmap", "args": command})
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
            ET.tostring(root, encoding="unicode")

    def selected_command(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.text() if item else None

    def all_commands(self) -> list:
        out = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 1)
            if item:
                out.append(item.text())
        return out

    def _remove_scan(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _cancel_scan(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.cancelRequested.emit(row)
            self._set_status_item(row, "Cancelled")

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        item = self.table.item(row, 1)
        if item:
            self.reuseRequested.emit(item.text())
