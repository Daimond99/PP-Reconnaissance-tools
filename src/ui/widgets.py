"""
Recon Tool - Widgets Module
เก็บ UI components ทั้งหมด: Sidebar, TopBar, และ Pages
"""

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QTextEdit, QStackedWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
    QSizePolicy, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt, QByteArray
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from src.config import (
    TERMINAL_FONT_FAMILY, TERMINAL_FONT_SIZE,
    TOOL_LIST, WARHEAD_PROFILES, OPERATION_MODES,
    DIRECT_TOOL_CONTENT, LLM_DEMO_TEXT,
    BG, PANEL_LIGHT, PURPLE, TEXT, TEXT_DIM, BORDER, CONSOLE_BG, CONSOLE_TEXT,
    BG_PANEL_2, TEXT_MUTE, ORANGE, ACCENT_GREEN,
)

from src.core.tool_manager import get_tool_manager
from src.ui.llm_mode import LLMModeTab
from src.ui.tool_selection import ToolSelectionTab
from src.ui.wizard_console import WizardConsoleTab
from src.validation.common import parse_command_line


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


def wrap_in_terminal(widget: QWidget, icon: str, title: str) -> QFrame:
    """Wrap a console widget in the mockup's terminal-window chrome
    (header bar with icon + title) without altering the wrapped widget."""
    frame = QFrame()
    frame.setObjectName("TermWindow")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    bar = QFrame()
    bar.setObjectName("TermBar")
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(14, 8, 14, 8)
    bar_layout.setSpacing(8)
    icon_label = QLabel(icon)
    icon_label.setObjectName("TermIcon")
    title_label = QLabel(title)
    title_label.setObjectName("TermTitle")
    bar_layout.addWidget(icon_label)
    bar_layout.addWidget(title_label)
    bar_layout.addStretch()

    layout.addWidget(bar)
    layout.addWidget(widget, 1)
    return frame


# ============================================================================
# SIDEBAR - แถบด้านข้าง (collapsible icon nav, matches Mission Control mockup)
# ============================================================================

class Sidebar(QFrame):
    navigate = Signal(int)
    """แถบนำทางด้านซ้าย — พับ/ขยายได้, 7 หน้า + Settings"""

    NAV_ITEMS = [
        ("✦", "Wizard Console"),
        ("☐", "Input Management"),
        ("✎", "Command Editor"),
        ("⚙", "Raw Output"),
        ("▦", "Results Display"),
        ("◈", "LLM Mode"),
        ("⚔", "Tool Selection"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setProperty("collapsed", False)
        self._collapsed = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setObjectName("SidebarToggle")
        self.toggle_btn.setFixedSize(28, 28)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_collapsed)
        top_row.addWidget(self.toggle_btn)
        top_row.addStretch()
        layout.addLayout(top_row)
        layout.addSpacing(8)

        self.nav_buttons: list[QPushButton] = []
        self.nav_labels: list[QLabel] = []
        for index, (icon, title) in enumerate(self.NAV_ITEMS):
            btn = self._nav_button(icon, title)
            btn.setProperty("selected", index == 0)
            btn.clicked.connect(lambda _=False, i=index: self._select_nav(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        divider = QFrame()
        divider.setObjectName("HLine")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(6)

        self.settings_btn = self._nav_button("⚙", "Settings", settings=True)
        layout.addWidget(self.settings_btn)

    def _nav_button(self, icon: str, title: str, settings: bool = False) -> QPushButton:
        btn = QPushButton(f"  {icon}   {title}")
        btn.setObjectName("SidebarSettingsItem" if settings else "SidebarNavItem")
        btn.setFixedHeight(38)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("icon_glyph", icon)
        btn.setProperty("full_label", title)
        return btn

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self.setProperty("collapsed", self._collapsed)
        _restyle(self)
        self.setFixedWidth(68 if self._collapsed else 220)
        for btn in (*self.nav_buttons, self.settings_btn):
            icon = btn.property("icon_glyph")
            title = btn.property("full_label")
            btn.setText(f"  {icon}" if self._collapsed else f"  {icon}   {title}")

    def _select_nav(self, index: int) -> None:
        for item_index, button in enumerate(self.nav_buttons):
            button.setProperty("selected", item_index == index)
            _restyle(button)
        self.navigate.emit(index)


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
        target_row = QHBoxLayout()
        target_row.setSpacing(8)
        self.target_input = QLineEdit("192.168.1.0/24")
        self.target_input.setObjectName("MissionInput")
        self.target_input.setFixedWidth(190)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setObjectName("BrowseButton")
        target_row.addWidget(self.target_input)
        target_row.addWidget(self.browse_btn)
        target_col.addLayout(target_row)
        row1.addLayout(target_col)

        mode_col = QVBoxLayout()
        mode_col.setSpacing(5)
        mode_col.addWidget(self._field_label("OPERATION MODE"))
        self.opmode_combo = QComboBox()
        self.opmode_combo.setObjectName("MissionCombo")
        self.opmode_combo.addItems(OPERATION_MODES)
        self.opmode_combo.setFixedWidth(180)
        mode_col.addWidget(self.opmode_combo)
        row1.addLayout(mode_col)

        tool_col = QVBoxLayout()
        tool_col.setSpacing(5)
        tool_col.addWidget(self._field_label("TOOL / SCANNER"))
        tm = get_tool_manager()
        tool_names = [info.display_name for info in tm.tools.values()]
        self.tool_combo = QComboBox()
        self.tool_combo.setObjectName("MissionCombo")
        self.tool_combo.addItems(tool_names if tool_names else TOOL_LIST)
        self.tool_combo.setFixedWidth(220)
        tool_col.addWidget(self.tool_combo)
        row1.addLayout(tool_col)

        profile_col = QVBoxLayout()
        profile_col.setSpacing(5)
        profile_col.addWidget(self._field_label("WARHEAD PROFILE"))
        self.warhead_combo = QComboBox()
        self.warhead_combo.setObjectName("MissionCombo")
        self.warhead_combo.addItems(WARHEAD_PROFILES)
        self.warhead_combo.setFixedWidth(180)
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


# ============================================================================
# PAGES - แต่ละหน้าใน Main Content Area
# ============================================================================

class RawOutputTab(QWidget):
    """Tab สำหรับแสดง output ดิบจากคำสั่งที่รันผ่าน gated pipeline เท่านั้น
    (read-only log — ไม่มี shell ของตัวเอง, ไม่รับคำสั่งตรงจากผู้ใช้)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(10)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("LogStatusDot")
        self.status_text = QLabel("idle")
        self.status_text.setObjectName("LogStatus")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        layout.addLayout(status_row)

        font = QFont(TERMINAL_FONT_FAMILY, 11)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setAcceptRichText(False)
        self.output_area.setFont(font)
        self.output_area.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; border-radius: 4px; padding: 20px 24px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
        """)
        self.output_area.setPlaceholderText("Command output from gated executions will appear here")
        self.console = self.output_area

        self.term_frame = wrap_in_terminal(self.output_area, "&gt;_", "root@recon: ~/output")
        layout.addWidget(self.term_frame, 1)

    def set_running(self, running: bool) -> None:
        self.status_text.setText("running" if running else "idle")
        self.status_text.setProperty("running", running)
        self.status_dot.setProperty("running", running)
        _restyle(self.status_text)
        _restyle(self.status_dot)

    def append_log(self, text: str):
        """เขียน log ที่มาจากคำสั่งซึ่งผ่าน ConfirmationGate ไปเเล้วเท่านั้น"""
        self.output_area.append(text)
        scrollbar = self.output_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ---------------------------------------------------------------------------
# Results Display — Zenmap-style host list + expandable detail tree.
#
# No structured multi-host parser output exists yet in src/tools/*/parser.py
# (only a flat open-ports list for nmap) — this panel ships with the same
# kind of placeholder dataset the mockup uses and exposes set_hosts() for
# real data to be wired in later.
# ---------------------------------------------------------------------------

_DEMO_HOSTS = [
    {
        "icon": "\U0001F427", "host": "scanme.nmap.org", "ip": "205.217.153.62",
        "state": "up", "open": 3, "filtered": 0, "closed": 2, "scanned": 5,
        "uptime": "3920659", "lastboot": "Sat Oct 27 10:38:07 2007",
        "hostname": "scanme.nmap.org - PTR",
        "os": "Linux 2.6.20-1 (Fedora Core 5)", "accuracy": 100,
        "ports": [
            {"port": 22, "proto": "tcp", "service": "ssh", "state": "open"},
            {"port": 80, "proto": "tcp", "service": "http", "state": "open"},
            {"port": 9929, "proto": "tcp", "service": "nping-echo", "state": "open"},
        ],
    },
    {
        "icon": "\U0001F5A5", "host": "171.67.22.3", "ip": "171.67.22.3",
        "state": "up", "open": 2, "filtered": 1, "closed": 0, "scanned": 3,
        "uptime": "-", "lastboot": "unknown", "hostname": "-",
        "os": "Unknown", "accuracy": 0,
        "ports": [
            {"port": 80, "proto": "tcp", "service": "http", "state": "open"},
            {"port": 443, "proto": "tcp", "service": "https", "state": "open"},
            {"port": 8080, "proto": "tcp", "service": "http-proxy", "state": "filtered"},
        ],
    },
    {
        "icon": "\U0001F512", "host": "10.0.0.10", "ip": "10.0.0.10",
        "state": "up", "open": 1, "filtered": 0, "closed": 1, "scanned": 2,
        "uptime": "-", "lastboot": "unknown", "hostname": "-",
        "os": "Unknown", "accuracy": 0,
        "ports": [{"port": 22, "proto": "tcp", "service": "ssh", "state": "open"}],
    },
]


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
        self.host_list.setFixedWidth(260)
        self.host_list.currentRowChanged.connect(self._on_host_selected)
        layout.addWidget(self.host_list)

        self.detail_tree = QTreeWidget()
        self.detail_tree.setObjectName("ZmDetailTree")
        self.detail_tree.setHeaderHidden(True)
        self.detail_tree.setIndentation(16)
        layout.addWidget(self.detail_tree, 1)

        self.set_hosts(_DEMO_HOSTS)

    def set_hosts(self, hosts: list[dict]) -> None:
        """Replace the displayed host set (e.g. once real scan-result
        parsing produces structured per-host data)."""
        self._hosts = hosts
        self.host_list.clear()
        for host in hosts:
            item = QListWidgetItem(f"{host['icon']}  {host['host']}")
            self.host_list.addItem(item)
        if hosts:
            self.host_list.setCurrentRow(0)
        else:
            self.detail_tree.clear()

    def _on_host_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._hosts):
            return
        self._selected_index = row
        self._render_detail(self._hosts[row])

    def _kv_item(self, parent: QTreeWidgetItem, key: str, value: str) -> None:
        child = QTreeWidgetItem(parent)
        row = QWidget()
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
        self._kv_item(addr_node, "IPv6", "-")
        self._kv_item(addr_node, "MAC", "-")

        hostname_node = QTreeWidgetItem(self.detail_tree, ["Hostnames"])
        self._kv_item(hostname_node, "Name - Type", host["hostname"])

        os_node = QTreeWidgetItem(self.detail_tree, ["Operating System"])
        self._kv_item(os_node, "Name", host["os"])
        self._accuracy_row(os_node, host["accuracy"])

        ports_node = QTreeWidgetItem(self.detail_tree, ["Ports used"])
        self._ports_table(ports_node, host["ports"])

        for node in (status_node, addr_node, hostname_node, os_node, ports_node):
            node.setExpanded(node is not ports_node)


class InputManagementTab(QWidget):
    """Tab สำหรับ Input Management — editable parameter table"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Parameter")
        self.add_btn.setObjectName("ActionButton")
        self.add_btn.clicked.connect(self._add_row)
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Key", "Value", "Description"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
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
        """)
        layout.addWidget(self.table, 1)

        for key, value, desc in (
            ("target", "192.168.1.0/24", "CIDR range"),
            ("ports", "1-65535", "Full port range"),
            ("rate", "10000", "Packets / sec"),
            ("timeout", "5s", "Per-host timeout"),
        ):
            self._add_row(key, value, desc)

    def _add_row(self, key: str = "", value: str = "", desc: str = "") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(key))
        self.table.setItem(row, 1, QTableWidgetItem(value))
        self.table.setItem(row, 2, QTableWidgetItem(desc))


class CommandEditorTab(QWidget):
    """Tab สำหรับ Command Editor"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        preview_label = QLabel("Command Preview")
        preview_label.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:600;")
        layout.addWidget(preview_label)

        self.preview_box = QLabel("nmap -sS -p- -sV 192.168.1.0/24")
        self.preview_box.setObjectName("CommandPreviewBox")
        self.preview_box.setFixedHeight(40)
        self.preview_box.setStyleSheet(f"""
            background-color:{CONSOLE_BG}; color:{CONSOLE_TEXT};
            font-family:'Consolas','Courier New',monospace;
            font-size:13.5px; padding:12px 16px; border-radius:4px;
            border:1px solid {BORDER};
        """)
        layout.addWidget(self.preview_box)

        self.edit_area = QTextEdit()
        self.edit_area.setObjectName("EditCommandArea")
        self.edit_area.setPlainText("nmap -sS -p- -sV 192.168.1.0/24")
        self.edit_area.setMinimumHeight(220)
        layout.addWidget(self.edit_area, 1)

        self.validate_status = QLabel("")
        self.validate_status.setStyleSheet(f"font-size:12.5px;")
        layout.addWidget(self.validate_status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.reset_btn = QPushButton("Reset to Wizard Output")
        self.reset_btn.setObjectName("ActionButton")
        self.validate_btn = QPushButton("Validate Syntax")
        self.validate_btn.setObjectName("ActionButton")
        self.validate_btn.clicked.connect(self._validate_syntax)
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.validate_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _validate_syntax(self) -> None:
        command = self.edit_area.toPlainText().strip()
        ok, err, _argv = parse_command_line(command)
        if ok:
            self.validate_status.setText("[✓] Syntax OK")
            self.validate_status.setStyleSheet(f"font-size:12.5px; color:{ACCENT_GREEN};")
        else:
            self.validate_status.setText(f"[!] {err}")
            self.validate_status.setStyleSheet("font-size:12.5px; color:#ff5555;")


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
        self.wizard_tab = WizardConsoleTab()
        self.input_tab = InputManagementTab()
        self.cmd_editor_tab = CommandEditorTab()
        self.raw_output_tab = RawOutputTab()
        self.results_tab = ResultsDisplayTab()
        self.llm_tab = LLMModeTab()
        self.tool_selection_tab = ToolSelectionTab()

        # Order matches Sidebar.NAV_ITEMS / navigate(index) 0-6.
        self.stack.addWidget(wrap_in_terminal(self.wizard_tab, "&gt;_", "root@recon: ~/wizard"))
        self.stack.addWidget(self.input_tab)
        self.stack.addWidget(self.cmd_editor_tab)
        self.stack.addWidget(self.raw_output_tab)
        self.stack.addWidget(self.results_tab)
        self.stack.addWidget(wrap_in_terminal(self.llm_tab, "✦", "recon-assistant: ~"))
        self.stack.addWidget(self.tool_selection_tab)

        self.raw_output_tab.set_running(False)
        self.wizard_tab.executionStarted.connect(lambda: self.raw_output_tab.set_running(True))
        self.wizard_tab.executionFinished.connect(lambda: self.raw_output_tab.set_running(False))
