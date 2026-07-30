"""
Recon Tool - Widgets Module
เก็บ UI components ทั้งหมด: Sidebar, TopBar, และ Pages
"""

import os

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
from src.ui.terminal import InteractiveTerminal
from src.ui.pty_terminal import PtyTerminal, PTY_AVAILABLE
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
        "Command Editor",
        "Raw Output",
        "Results Display",
        "LLM Mode",
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
        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("SidebarToggle")
        self.toggle_btn.setIcon(svg_icon("M4 6h16M4 12h16M4 18h16", color="#b8b8c4"))
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_collapsed)
        top_row.addWidget(self.toggle_btn)
        top_row.addStretch()
        layout.addLayout(top_row)
        layout.addSpacing(8)

        self.nav_buttons: list[QPushButton] = []
        for index, title in enumerate(self.NAV_ITEMS):
            btn = self._nav_button(title)
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

        self.settings_btn = self._nav_button("Settings", settings=True)
        layout.addWidget(self.settings_btn)

    def _nav_button(self, title: str, settings: bool = False) -> QPushButton:
        btn = QPushButton(title)
        btn.setObjectName("SidebarSettingsItem" if settings else "SidebarNavItem")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("full_label", title)
        return btn

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self.setProperty("collapsed", self._collapsed)
        _restyle(self)
        self.setFixedWidth(64 if self._collapsed else 220)
        for btn in (*self.nav_buttons, self.settings_btn):
            title = btn.property("full_label")
            btn.setText(title[0] if self._collapsed else title)

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
        # Editable combo = text field + dropdown arrow holding the history
        # of targets the user has typed and executed.
        self.target_input = QComboBox()
        self.target_input.setObjectName("MissionCombo")
        self.target_input.setEditable(True)
        self.target_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.target_input.setFixedWidth(230)
        self.target_input.addItem("192.168.1.0/24")
        self.target_input.setCurrentText("192.168.1.0/24")
        target_col.addWidget(self.target_input)
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

    def target_text(self) -> str:
        return self.target_input.currentText().strip()

    def add_target_history(self, target: str) -> None:
        target = (target or "").strip()
        if not target:
            return
        if self.target_input.findText(target) == -1:
            self.target_input.insertItem(0, target)
        self.target_input.setCurrentText(target)


# ============================================================================
# PAGES - แต่ละหน้าใน Main Content Area
# ============================================================================

class RawOutputTab(QWidget):
    """Plain interactive bash terminal — no app-injected text, no mirroring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        self.terminal = InteractiveTerminal()
        self.console = self.terminal
        layout.addWidget(wrap_in_terminal(self.terminal), 1)


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
        self.host_list.setFixedWidth(260)
        self.host_list.currentRowChanged.connect(self._on_host_selected)
        layout.addWidget(self.host_list)

        self.detail_tree = QTreeWidget()
        self.detail_tree.setObjectName("ZmDetailTree")
        self.detail_tree.setHeaderHidden(True)
        self.detail_tree.setIndentation(16)
        layout.addWidget(self.detail_tree, 1)

        # Empty until a real nmap scan populates it via set_hosts().
        self.set_hosts([])

    def set_hosts(self, hosts: list[dict]) -> None:
        """Replace the displayed host set (e.g. once real scan-result
        parsing produces structured per-host data)."""
        self._hosts = hosts
        self.host_list.clear()
        for host in hosts:
            item = QListWidgetItem(host["host"])
            self.host_list.addItem(item)
        if hosts:
            self.host_list.setCurrentRow(0)
        else:
            self.detail_tree.clear()
            placeholder = QTreeWidgetItem(
                self.detail_tree,
                ["No results yet — run an nmap scan to see host details here."],
            )
            placeholder.setDisabled(True)

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

    @staticmethod
    def _make_wizard_terminal():
        """
        Wizard Console runs the standalone 'chain_wizard' chain CLI
        (scan → ranked plan → hydra → cred harvest → post-exploit).

        Preferred path (Windows): a real ConPTY-backed terminal (PtyTerminal)
        running it inside Ubuntu WSL — full color, working sudo prompts, TAB
        completion; identical to a standalone Ubuntu WSL terminal. `exec bash`
        keeps the pane usable after the wizard exits.

        Fallback: the plain-pipe InteractiveTerminal (no color/sudo TTY) when
        pywinpty/pyte are unavailable.
        """
        wsl_dir = "/mnt/d/TheRecon/chain_wizard"
        launch = f"cd '{wsl_dir}' && python3 -m wizard.main; exec bash -l"

        if PTY_AVAILABLE and os.name == "nt":
            argv = ["wsl.exe", "-d", "Ubuntu", "bash", "-lc", launch]
            return PtyTerminal(argv)

        if os.name == "nt":
            return InteractiveTerminal(
                "wsl.exe", ["-e", "bash", "-lc", f"cd '{wsl_dir}' && python3 -m wizard.main"]
            )
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        local_dir = os.path.join(repo_root, "chain_wizard")
        return InteractiveTerminal(
            "bash", ["-lc", f"cd '{local_dir}' && python3 -m wizard.main"]
        )

    def _build_pages(self):
        # Wizard Console runs the 'chain_wizard' chain CLI in a real ConPTY
        # terminal (see _make_wizard_terminal). The older native wizard pages
        # (wizard_terminal.py / wizard_console.py / src/wizard/engine.py) have
        # been removed — this is the only wizard path now.
        self.wizard_tab = self._make_wizard_terminal()
        self.input_tab = InputManagementTab()
        self.cmd_editor_tab = CommandEditorTab()
        self.raw_output_tab = RawOutputTab()
        self.results_tab = ResultsDisplayTab()
        # LLM page is a plain real bash terminal — the user wires it to an AI
        # API themselves (e.g. `llm`, `claude`, curl to an endpoint).
        self.llm_tab = InteractiveTerminal()

        # Order matches Sidebar.NAV_ITEMS / navigate(index) 0-5.
        self.stack.addWidget(wrap_in_terminal(self.wizard_tab))
        self.stack.addWidget(self.input_tab)
        self.stack.addWidget(self.cmd_editor_tab)
        self.stack.addWidget(self.raw_output_tab)
        self.stack.addWidget(self.results_tab)
        self.stack.addWidget(wrap_in_terminal(self.llm_tab))
