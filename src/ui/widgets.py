"""
Recon Tool - Widgets Module
เก็บ UI components ทั้งหมด: Sidebar, TopBar, และ Pages
"""

import xml.etree.ElementTree as ET
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QStackedWidget, QHBoxLayout, QVBoxLayout,
    QSizePolicy, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox,
)
from PySide6.QtCore import Signal, Qt, QByteArray
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from src.config import (
    WARHEAD_BY_TOOL, OPERATION_MODES,
    PURPLE, TEXT, TEXT_DIM, BORDER,
    BG_PANEL_2, TEXT_MUTE, ORANGE, ACCENT_GREEN,
)

from src.core.tool_manager import get_tool_manager
from src.ui.terminal_tabs import TerminalTabsWidget, make_terminal


def svg_icon(path: str, color: str = "#edf0f5", size: int = 16) -> QIcon:
    """Build a crisp, dependency-free SVG icon for custom controls."""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d="{path}" fill="none" stroke="{color}" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round"/>
    </svg>'''
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _restyle(widget: QWidget) -> None:
    """Force a stylesheet re-evaluation after a dynamic property changes."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def wrap_in_terminal(widget: QWidget) -> QFrame:
    """Wrap a console widget in plain terminal chrome — a blank rounded
    frame, no header bar, no title text."""
    frame = QFrame()
    frame.setObjectName("TermWindow")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(widget, 1)
    return frame


# ============================================================================
# SIDEBAR - แถบด้านข้าง (collapsible icon nav, matches Mission Control mockup)
# ============================================================================

class Sidebar(QFrame):
    navigate = Signal(int)
    """แถบนำทางด้านซ้าย — พับ/ขยายได้, ข้อความล้วนไม่มี emoji"""

    NAV_ITEMS = [
        "Wizard Console",
        "Input Management",
        "Raw Output",
        "Results Display",
        "LLM Mode",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(2)

        # The collapse toggle and Settings live in the title bar now (top-left),
        # so the sidebar itself is just the nav list.
        self.nav_buttons: list[QPushButton] = []
        for index, title in enumerate(self.NAV_ITEMS):
            btn = self._nav_button(title)
            btn.setProperty("selected", index == 0)
            btn.clicked.connect(lambda _=False, i=index: self._select_nav(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

    def _nav_button(self, title: str, settings: bool = False) -> QPushButton:
        btn = QPushButton(title)
        btn.setObjectName("SidebarSettingsItem" if settings else "SidebarNavItem")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("full_label", title)
        return btn

    def _select_nav(self, index: int) -> None:
        for item_index, button in enumerate(self.nav_buttons):
            button.setProperty("selected", item_index == index)
            _restyle(button)
        self.navigate.emit(index)

    def select_index(self, index: int) -> None:
        """Programmatic navigation (e.g. auto-jump to Raw Output on
        Execute) — same effect as the user clicking that nav item."""
        self._select_nav(index)


# ============================================================================
# MISSION BAR (formerly TopBar) — Target / Mode / Tool / Warhead + Execute
# ============================================================================

class TopBar(QFrame):
    """แถบด้านบนสำหรับ Target, Mode และ Command"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MissionBar")
        self._build()

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("MissionFieldLabel")
        return lbl

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 14, 22, 14)
        outer.setSpacing(12)

        # row1: Target, Mode, Tool
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        target_col = QVBoxLayout()
        target_col.setSpacing(5)
        target_col.addWidget(self._field_label("TARGET"))
        self.target_input = QLineEdit()
        self.target_input.setObjectName("MissionCombo")
        self.target_input.setFixedWidth(150)
        self.target_input.setText("192.168.1.0/24")
        target_col.addWidget(self.target_input)
        row1.addLayout(target_col)

        mode_col = QVBoxLayout()
        mode_col.setSpacing(5)
        mode_col.addWidget(self._field_label("OPERATION MODE"))
        self.opmode_combo = QComboBox()
        self.opmode_combo.setObjectName("MissionCombo")
        # Defaults to "Wizard Mode" (index 0 of OPERATION_MODES) — the
        # command box/Execute stay disabled until Direct Tool Mode is
        # explicitly picked (see main_window._on_opmode_change).
        self.opmode_combo.addItems(OPERATION_MODES)
        self.opmode_combo.setFixedWidth(150)
        mode_col.addWidget(self.opmode_combo)
        row1.addLayout(mode_col)

        tool_col = QVBoxLayout()
        tool_col.setSpacing(5)
        tool_col.addWidget(self._field_label("TOOLS"))
        tm = get_tool_manager()
        tool_names = [info.display_name for info in tm.tools.values()]
        self.tool_combo = QComboBox()
        self.tool_combo.setObjectName("MissionCombo")
        self.tool_combo.addItems(tool_names)
        self.tool_combo.setFixedWidth(130)
        tool_col.addWidget(self.tool_combo)
        row1.addLayout(tool_col)

        profile_col = QVBoxLayout()
        profile_col.setSpacing(5)
        profile_col.addWidget(self._field_label("WARHEAD PROFILE"))
        self.warhead_combo = QComboBox()
        self.warhead_combo.setObjectName("MissionCombo")
        self.warhead_combo.addItems(WARHEAD_BY_TOOL.get(tool_names[0] if tool_names else "", {}).keys())
        self.warhead_combo.setFixedWidth(220)
        profile_col.addWidget(self.warhead_combo)
        row1.addLayout(profile_col)

        row1.addStretch()
        outer.addLayout(row1)

        # row2: command preview/edit + execute
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        self.command_input = QLineEdit("masscan -p1-65535 --rate=10000 192.168.1.0/24")
        self.command_input.setObjectName("CmdPreview")
        self.command_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.execute_btn = QPushButton("▶  EXECUTE MISSION")
        self.execute_btn.setObjectName("ExecuteButton")

        row2.addWidget(self.command_input, 1)
        row2.addWidget(self.execute_btn)
        outer.addLayout(row2)

    def target_text(self) -> str:
        return self.target_input.text().strip()

    def set_warhead_profiles(self, tool: str) -> None:
        """Repopulate WARHEAD PROFILE with just `tool`'s own warheads —
        each tool has its own attack profiles (stealth/critical/quality),
        not a single shared nmap-flavored list. Signals blocked during the
        swap so this doesn't fire a stray currentTextChanged for an
        in-between/empty combo state while it's being rebuilt."""
        self.warhead_combo.blockSignals(True)
        self.warhead_combo.clear()
        self.warhead_combo.addItems(WARHEAD_BY_TOOL.get(tool, {}).keys())
        self.warhead_combo.blockSignals(False)


# ============================================================================
# PAGES - แต่ละหน้าใน Main Content Area
# ============================================================================

class RawOutputTab(QWidget):
    """Display-only output surface — same backend the Wizard Console uses
    (XtermTerminal → PtyTerminal → InteractiveTerminal), but with keyboard
    input dropped (`read_only=True`) so it's never typed into directly. The
    top-bar Execute button sends its gated command here instead of a
    QMessageBox, so the scan runs with real color/output in a real terminal.

    The terminal itself (one QWebEngineView = one Chromium renderer process,
    plus a real wsl.exe/bash PTY) is not spawned until this page is actually
    needed — first shown, or first fed a command — instead of eagerly at app
    startup. `commandDone` is a stable signal owned by this tab (not the
    inner terminal), so callers can connect to it once at construction and
    it keeps working correctly regardless of when the real terminal ends up
    getting created underneath."""

    commandDone = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(0)

        self.terminal = None
        self.console = None
        self._placeholder = QLabel("Idle — display-only, waiting for a command to run here.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {TEXT_MUTE};")
        self._layout.addWidget(self._placeholder, 1)

    def _ensure_terminal(self) -> None:
        if self.terminal is not None:
            return
        self.terminal = make_terminal("shell", read_only=True)
        self.console = self.terminal
        self._layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._placeholder = None
        self._layout.addWidget(wrap_in_terminal(self.terminal), 1)
        done_signal = getattr(self.terminal, "commandDone", None)
        if done_signal is not None:
            done_signal.connect(self.commandDone.emit)

    def showEvent(self, event) -> None:
        self._ensure_terminal()
        super().showEvent(event)

    def run_command(self, command: str):
        """Send an already-gated command into the live shell as if typed.
        Returns a completion token if the backend supports done-detection
        (xterm.js), else None."""
        self._ensure_terminal()
        run = getattr(self.terminal, "run_command", None)
        if callable(run):
            return run(command)
        write = getattr(self.terminal, "write_text", None)
        if callable(write):
            write(command)
        return None

    def interrupt(self) -> None:
        if self.terminal is None:
            return
        interrupt = getattr(self.terminal, "interrupt", None)
        if callable(interrupt):
            interrupt()

    def focus(self) -> None:
        self._ensure_terminal()
        focus = getattr(self.terminal, "focus", None)
        if callable(focus):
            focus()


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


class MainContentArea(QWidget):
    """พื้นที่หลักสำหรับแสดงหน้าต่างๆ ผ่าน Sidebar navigation เท่านั้น
    (ไม่มี tab bar ซ้ำซ้อน — ตรงกับ mockup)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self._build_pages()
        layout.addWidget(self.stack)

    def _build_pages(self):
        # Wizard Console is a VS Code-style tabbed terminal (TerminalTabsWidget):
        # first tab runs the 'chain_wizard' chain CLI, `+`/`⌄` open more Wizard
        # or plain Shell tabs. Each tab picks its own backend (XtermTerminal →
        # PtyTerminal → InteractiveTerminal). The older native wizard pages
        # (wizard_terminal.py / wizard_console.py / src/wizard/engine.py) were
        # removed — this is the only wizard path now.
        self.wizard_tab = TerminalTabsWidget()
        self.input_tab = InputManagementTab()
        self.raw_output_tab = RawOutputTab()
        self.results_tab = ResultsDisplayTab()
        # LLM page — same tabbed-terminal container as Wizard Console, two
        # profiles instead: "llm-nmap" (auto-cd's into tools/llm-tools-nmap,
        # offers to set an API key if none is stored yet) and "opencode"
        # (the OpenCode agent CLI, PATH-restricted to TheRecon's 6
        # authorized tools — see terminal_tabs._opencode_launch). Ungated by
        # design, same as before.
        self.llm_tab = TerminalTabsWidget(fixed=True, profiles=[
            ("New LLM Nmap tab", "llm-nmap", "LLM"),
            ("New OpenCode tab", "opencode", "OpenCode"),
        ])

        # Order matches Sidebar.NAV_ITEMS / navigate(index) 0-4.
        self.stack.addWidget(wrap_in_terminal(self.wizard_tab))
        self.stack.addWidget(self.input_tab)
        self.stack.addWidget(self.raw_output_tab)
        self.stack.addWidget(self.results_tab)
        self.stack.addWidget(wrap_in_terminal(self.llm_tab))
