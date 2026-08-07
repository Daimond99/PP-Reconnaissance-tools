"""ResultsDisplayTab — Zenmap-style split view (host list + detail tree) for
parsed nmap/masscan scans and hydra/ncrack credentials."""

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QHBoxLayout,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from src.config import PURPLE, TEXT_DIM, BORDER, TEXT_MUTE, ORANGE, ACCENT_GREEN


# ---------------------------------------------------------------------------
# Results Display — Zenmap-style host list + expandable detail tree.
#
# Starts empty. Real per-host data is injected via set_hosts() once an nmap
# scan produces structured output.
# ---------------------------------------------------------------------------


class ResultsDisplayTab(QWidget):
    """Tab สำหรับแสดง Results — Zenmap-style split view"""

    STATE_COLOR = {"open": ACCENT_GREEN, "filtered": ORANGE, "closed": TEXT_MUTE}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hosts: list[dict] = []
        self._selected_index = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        self.host_list = QListWidget()
        self.host_list.setObjectName("ZmHostList")
        self.host_list.setFixedWidth(190)
        # Display-only — no rename-on-double-click, no typing into rows.
        self.host_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Rows carry a timestamp suffix now (see add_scan_results) — elide
        # instead of growing a horizontal scrollbar if one still overflows.
        self.host_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.host_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.host_list.currentRowChanged.connect(self._on_host_selected)
        layout.addWidget(self.host_list)

        self.detail_tree = QTreeWidget()
        self.detail_tree.setObjectName("ZmDetailTree")
        self.detail_tree.setHeaderHidden(True)
        self.detail_tree.setIndentation(16)
        # Detail rows are read-only info, not clickable controls — only the
        # section expand/collapse arrows should respond to a click.
        self.detail_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.detail_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Display-only — no in-place editing of any detail row.
        self.detail_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.detail_tree, 1)

        # Empty until a real nmap scan populates it via set_hosts().
        self.set_hosts([])

    def set_hosts(self, hosts: list[dict]) -> None:
        """Replace the displayed host set (e.g. once real scan-result
        parsing produces structured per-host data)."""
        self._hosts = hosts
        self.host_list.clear()
        for host in hosts:
            item = QListWidgetItem(host.get("label", host["host"]))
            self.host_list.addItem(item)
        if hosts:
            self.host_list.setCurrentRow(0)
        else:
            self.detail_tree.clear()
            placeholder = QTreeWidgetItem(
                self.detail_tree,
                ["No results yet — run a scan or credential attack to see details here."],
            )
            placeholder.setDisabled(True)

    def add_scan_results(self, new_hosts: list[dict]) -> None:
        """Append `new_hosts` (freshly parsed from one nmap/masscan scan) as
        new rows — every scan run gets its own entry, even a repeat scan of
        the same IP with different flags/warhead, so nothing gets silently
        overwritten. Selects the first of the newly-added hosts."""
        if not new_hosts:
            return
        first_new_row = len(self._hosts)
        self._hosts.extend(new_hosts)
        self.set_hosts(self._hosts)
        self.host_list.setCurrentRow(first_new_row)

    def add_credential_results(self, tool: str, target: str, creds: list[dict],
                                stamp: str) -> None:
        """Append one row for a completed hydra/ncrack run's found
        credentials — a differently-shaped entry (`kind: "credentials"`)
        rendered by `_render_credentials_detail` instead of the nmap/
        masscan host-detail view, but living in the same host_list/
        detail_tree split view so every tool's results show up in one
        place."""
        entry = {
            "host": target,
            "label": f"{tool} · {target} · {stamp}",
            "kind": "credentials",
            "tool": tool,
            "credentials": creds,
        }
        first_new_row = len(self._hosts)
        self._hosts.append(entry)
        self.set_hosts(self._hosts)
        self.host_list.setCurrentRow(first_new_row)

    def _on_host_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._hosts):
            return
        self._selected_index = row
        entry = self._hosts[row]
        if entry.get("kind") == "credentials":
            self._render_credentials_detail(entry)
        else:
            self._render_detail(entry)

    def _kv_item(self, parent: QTreeWidgetItem, key: str, value: str) -> None:
        child = QTreeWidgetItem(parent)
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(8)
        key_lbl = QLabel(key)
        key_lbl.setObjectName("ZmKeyLabel")
        key_lbl.setFixedWidth(130)
        val_lbl = QLabel(value)
        val_lbl.setObjectName("ZmValueLabel")
        row_layout.addWidget(key_lbl)
        row_layout.addWidget(val_lbl, 1)
        self.detail_tree.setItemWidget(child, 0, row)

    def _accuracy_row(self, parent: QTreeWidgetItem, accuracy: int) -> None:
        child = QTreeWidgetItem(parent)
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(8)
        key_lbl = QLabel("Accuracy")
        key_lbl.setObjectName("ZmKeyLabel")
        key_lbl.setFixedWidth(130)

        bar = QFrame()
        bar.setObjectName("ZmAccuracyBar")
        bar.setFixedSize(220, 16)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        fill = QFrame()
        fill.setStyleSheet(f"background-color: {PURPLE}; border-radius: 3px;")
        fill.setFixedWidth(max(int(220 * accuracy / 100) - 2, 0))
        bar_layout.addWidget(fill)
        bar_layout.addStretch()
        label = QLabel(f"{accuracy}%", bar)
        label.setObjectName("ZmAccuracyLabel")
        label.setAlignment(Qt.AlignCenter)
        label.setGeometry(0, 0, 220, 16)

        row_layout.addWidget(key_lbl)
        row_layout.addWidget(bar)
        row_layout.addStretch()
        self.detail_tree.setItemWidget(child, 0, row)

    def _ports_table(self, parent: QTreeWidgetItem, ports: list[dict]) -> None:
        child = QTreeWidgetItem(parent)
        table = QTableWidget(len(ports), 4)
        table.setHorizontalHeaderLabels(["Port", "Protocol", "Service", "State"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.horizontalHeader().setStretchLastSection(True)
        table.setStyleSheet(
            f"background-color: transparent; color: {TEXT_DIM}; border: none; gridline-color: {BORDER};"
        )
        for row_idx, port in enumerate(ports):
            table.setItem(row_idx, 0, QTableWidgetItem(str(port["port"])))
            table.setItem(row_idx, 1, QTableWidgetItem(port["proto"]))
            table.setItem(row_idx, 2, QTableWidgetItem(port["service"]))
            state_item = QTableWidgetItem(port["state"])
            color = self.STATE_COLOR.get(port["state"], TEXT_DIM)
            state_item.setForeground(QColor(color))
            table.setItem(row_idx, 3, state_item)
        table.setFixedHeight(28 + 26 * len(ports))
        self.detail_tree.setItemWidget(child, 0, table)

    def _render_detail(self, host: dict) -> None:
        self.detail_tree.clear()

        status_node = QTreeWidgetItem(self.detail_tree, ["Host Status"])
        self._kv_item(status_node, "State", host["state"])
        self._kv_item(status_node, "Open ports", str(host["open"]))
        self._kv_item(status_node, "Filtered ports", str(host["filtered"]))
        self._kv_item(status_node, "Closed ports", str(host["closed"]))
        self._kv_item(status_node, "Scanned ports", str(host["scanned"]))
        self._kv_item(status_node, "Uptime", host["uptime"])
        self._kv_item(status_node, "Last boot", host["lastboot"])

        addr_node = QTreeWidgetItem(self.detail_tree, ["Addresses"])
        self._kv_item(addr_node, "IPv4", host["ip"])
        self._kv_item(addr_node, "IPv6", host.get("ipv6", "-"))
        self._kv_item(addr_node, "MAC", host.get("mac", "-"))

        hostname_node = QTreeWidgetItem(self.detail_tree, ["Hostnames"])
        self._kv_item(hostname_node, "Name - Type", host["hostname"])

        os_node = QTreeWidgetItem(self.detail_tree, ["Operating System"])
        self._kv_item(os_node, "Name", host["os"])
        self._accuracy_row(os_node, host["accuracy"])

        ports_node = QTreeWidgetItem(self.detail_tree, ["Ports used"])
        self._ports_table(ports_node, host["ports"])

        for node in (status_node, addr_node, hostname_node, os_node, ports_node):
            node.setExpanded(node is not ports_node)

    def _creds_table(self, parent: QTreeWidgetItem, creds: list[dict]) -> None:
        child = QTreeWidgetItem(parent)
        table = QTableWidget(len(creds), 5)
        table.setHorizontalHeaderLabels(["Host", "Port", "Service", "Login", "Password"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.horizontalHeader().setStretchLastSection(True)
        table.setStyleSheet(
            f"background-color: transparent; color: {TEXT_DIM}; border: none; gridline-color: {BORDER};"
        )
        for row_idx, cred in enumerate(creds):
            table.setItem(row_idx, 0, QTableWidgetItem(cred["host"]))
            table.setItem(row_idx, 1, QTableWidgetItem(str(cred["port"])))
            table.setItem(row_idx, 2, QTableWidgetItem(cred["service"]))
            login_item = QTableWidgetItem(cred["login"])
            login_item.setForeground(QColor(ACCENT_GREEN))
            table.setItem(row_idx, 3, login_item)
            pass_item = QTableWidgetItem(cred["password"])
            pass_item.setForeground(QColor(ACCENT_GREEN))
            table.setItem(row_idx, 4, pass_item)
        table.setFixedHeight(28 + 26 * len(creds))
        self.detail_tree.setItemWidget(child, 0, table)

    def _render_credentials_detail(self, entry: dict) -> None:
        self.detail_tree.clear()

        summary_node = QTreeWidgetItem(self.detail_tree, ["Attack Summary"])
        self._kv_item(summary_node, "Tool", entry["tool"])
        self._kv_item(summary_node, "Target", entry["host"])
        self._kv_item(summary_node, "Credentials found", str(len(entry["credentials"])))

        creds_node = QTreeWidgetItem(self.detail_tree, ["Credentials Found"])
        self._creds_table(creds_node, entry["credentials"])

        summary_node.setExpanded(True)
        creds_node.setExpanded(True)
