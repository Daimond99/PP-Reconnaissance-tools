"""
Recon Tool - Widgets Module
เก็บ UI components ทั้งหมด: Sidebar, TopBar, และ Tabs
"""

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QTextEdit, QTabWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QByteArray
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from src.config import (
    TERMINAL_FONT_FAMILY, TERMINAL_FONT_SIZE,
    TOOL_LIST, WARHEAD_PROFILES, OPERATION_MODES,
    DIRECT_TOOL_CONTENT, LLM_DEMO_TEXT,
    BG, PANEL_LIGHT, PURPLE, TEXT, TEXT_DIM, BORDER, CONSOLE_BG, CONSOLE_TEXT,
)

from src.core.tool_manager import get_tool_manager
from src.ui.llm_mode import LLMModeTab
from src.ui.tool_selection import ToolSelectionTab
from src.ui.wizard_console import WizardConsoleTab


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


# ============================================================================
# SIDEBAR - แถบด้านข้าง
# ============================================================================

class Sidebar(QFrame):
    navigate = Signal(int)
    """แถบด้านข้างสำหรับ Quick Actions และ Recent Scans"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        def section(title):
            lbl = QLabel(title)
            lbl.setObjectName("SidebarSection")
            lbl.setStyleSheet("padding: 0 0 14px 0; margin: 0; font-size: 14px;")
            return lbl

        def item(title):
            btn = QPushButton(title)
            btn.setObjectName("SidebarItem")
            btn.setFixedHeight(45)
            btn.setCursor(Qt.PointingHandCursor if hasattr(Qt, "PointingHandCursor") else Qt.ArrowCursor)
            return btn

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Search tools or sessions…")
        self.search_input.textChanged.connect(self._filter_sessions)
        layout.addWidget(self.search_input)
        layout.addWidget(section("Quick Actions"))

        self.nav_buttons = []
        for index, title in enumerate(["New Scan", "Input Management", "Command Editor"]):
            button = item(title)
            button.setProperty("selected", index == 0)
            button.clicked.connect(lambda _=False, i=index: self._select_nav(i))
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addSpacing(12)
        layout.addWidget(section("Recent Sessions"))
        self.session_buttons = []
        for title in ("Web surface review", "SSH service audit", "Windows assessment"):
            button = QPushButton(title)
            button.setObjectName("ChatItem")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False: self.navigate.emit(0))
            self.session_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch()

    def _select_nav(self, index: int) -> None:
        for item_index, button in enumerate(self.nav_buttons):
            button.setProperty("selected", item_index == index)
            button.style().unpolish(button)
            button.style().polish(button)
        self.navigate.emit(index)

    def _filter_sessions(self, text: str) -> None:
        query = text.strip().casefold()
        for button in (*self.nav_buttons, *self.session_buttons):
            button.setVisible(not query or query in button.text().casefold())


# ============================================================================
# TOP BAR - แถบด้านบน
# ============================================================================

class TopBar(QFrame):
    """แถบด้านบนสำหรับ Target, Mode และ Command"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        # remove setFixedHeight to let layout decide
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(14)

        # row1: Target, Mode, Tool
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 10) # เพิ่มระยะห่างด้านล่าง
        row1.setSpacing(20) # เพิ่มช่องว่างระหว่างวิดเจ็ต

        lbl_target = QLabel("Target:")
        lbl_target.setObjectName("BarLabel")

        self.target_input = QLineEdit("192.168.1.0/24")
        self.target_input.setFixedWidth(190)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setObjectName("BrowseButton")
        self.browse_btn.setFixedWidth(100)

        lbl_opmode = QLabel("Operation Mode:")
        lbl_opmode.setObjectName("BarLabel")

        self.opmode_combo = QComboBox()
        self.opmode_combo.addItems(OPERATION_MODES)
        self.opmode_combo.setFixedWidth(180)

        lbl_tool = QLabel("Tool / Scanner:")
        lbl_tool.setObjectName("BarLabel")

        tm = get_tool_manager()
        tool_names = [info.display_name for info in tm.tools.values()]
        
        self.tool_combo = QComboBox()
        self.tool_combo.addItems(tool_names if tool_names else TOOL_LIST)
        self.tool_combo.setFixedWidth(240)

        row1.addWidget(lbl_target)
        row1.addWidget(self.target_input)
        row1.addWidget(self.browse_btn)
        row1.addSpacing(10)
        row1.addWidget(lbl_opmode)
        row1.addWidget(self.opmode_combo)
        row1.addSpacing(10)
        row1.addWidget(lbl_tool)
        row1.addWidget(self.tool_combo)
        row1.addStretch()

        # row2: Profile, Command, Execute
        row2 = QHBoxLayout()
        row2.setSpacing(20) # เพิ่มช่องว่างระหว่างวิดเจ็ต

        lbl_warhead = QLabel("Warhead Profile:")
        lbl_warhead.setObjectName("BarLabel")

        self.warhead_combo = QComboBox()
        self.warhead_combo.addItems(WARHEAD_PROFILES)
        self.warhead_combo.setFixedWidth(180)

        lbl_cmd = QLabel("Command:")
        lbl_cmd.setObjectName("BarLabel")

        self.command_input = QLineEdit("masscan -p1-65535 --rate=10000 192.168.1.0/24")
        self.command_input.setObjectName("CommandInput")
        self.command_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.execute_btn = QPushButton("Execute Mission")
        self.execute_btn.setObjectName("ExecuteButton")

        row2.addWidget(lbl_warhead)
        row2.addWidget(self.warhead_combo)
        row2.addSpacing(10)
        row2.addWidget(lbl_cmd)
        row2.addWidget(self.command_input, 1)
        row2.addWidget(self.execute_btn)

        outer.addLayout(row1)
        outer.addLayout(row2)


# ============================================================================
# TABS - แต่ละ Tab ใน Main Content Area
# ============================================================================

class RawOutputTab(QWidget):
    """Tab สำหรับแสดง output ดิบจากคำสั่งที่รันผ่าน gated pipeline เท่านั้น
    (read-only log — ไม่มี shell ของตัวเอง, ไม่รับคำสั่งตรงจากผู้ใช้)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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
        layout.addWidget(self.output_area, 1)
        self.console = self.output_area

    def append_log(self, text: str):
        """เขียน log ที่มาจากคำสั่งซึ่งผ่าน ConfirmationGate ไปเเล้วเท่านั้น"""
        self.output_area.append(text)
        scrollbar = self.output_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class ResultsDisplayTab(QWidget):
    """Tab สำหรับแสดง Results"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; border-radius: 4px; padding: 20px 24px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13.5px;
        """)
        self.console.setPlaceholderText("Execute a scan to view results here")
        self.console.setPlainText("Execute a scan to view results here")
        layout.addWidget(self.console)


class InputManagementTab(QWidget):
    """Tab สำหรับ Input Management"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        grid = QGridLayout()
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(20)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        def field_label(text):
            lbl = QLabel(text)
            lbl.setObjectName("FieldLabel")
            lbl.setStyleSheet(f"color:{TEXT}; font-size:14px; font-weight:600; padding: 4px 0 8px 0;")
            return lbl

        def read_field(text):
            lbl = QLabel(text)
            lbl.setObjectName("InputField")
            lbl.setStyleSheet(f"""
                background-color:{PANEL_LIGHT}; color:{TEXT};
                border:1px solid {BORDER};
                padding:12px 16px; border-radius:4px; font-size:14px;
            """)
            lbl.setMinimumHeight(44)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            return lbl

        grid.addWidget(field_label("Target Input"), 0, 0)
        grid.addWidget(field_label("Target Type"), 0, 1)
        grid.addWidget(read_field("192.168.1.0/24"), 1, 0)
        grid.addWidget(read_field("CIDR Range"), 1, 1)
        grid.addWidget(field_label("YAML Profile"), 2, 0)
        grid.addWidget(field_label("Output Format"), 2, 1)
        grid.addWidget(read_field("Stealth Recon"), 3, 0)
        grid.addWidget(read_field("XML"), 3, 1)

        layout.addLayout(grid)
        layout.addSpacing(16)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        self.load_btn = QPushButton("Load Settings")
        self.load_btn.setObjectName("ActionButton")
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("ActionButton")
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("ActionButton")
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()

        layout.addLayout(btn_row)
        layout.addStretch()


class CommandEditorTab(QWidget):
    """Tab สำหรับ Command Editor"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(18)

        preview_label = QLabel("Command Preview")
        preview_label.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:600; margin-bottom: 4px;")
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

        edit_label = QLabel("Edit Command")
        edit_label.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:600; margin-top: 10px; margin-bottom: 4px;")
        layout.addWidget(edit_label)

        self.edit_area = QTextEdit()
        self.edit_area.setObjectName("EditCommandArea")
        self.edit_area.setPlainText("nmap -sS -p- -sV 192.168.1.0/24")
        self.edit_area.setMinimumHeight(160)
        layout.addWidget(self.edit_area, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        labels = ["Update Preview", "Back to Wizard", "Advanced Config", "Reset"]
        self.buttons = {}
        for label in labels:
            btn = QPushButton(label)
            btn.setObjectName("ActionButton")
            self.buttons[label] = btn
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)


class MainContentArea(QWidget):
    """พื้นที่หลักสำหรับแสดง Tabs ต่างๆ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {BG};
            }}
            QTabBar {{
                background: {BG};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {TEXT_DIM};
                font-size: 13px;
                font-weight: 600;
                padding: 14px 20px;
                border: none;
                min-width: 120px;
                white-space: nowrap;
            }}
            QTabBar::tab:selected {{
                color: white;
                border-bottom: 2px solid {PURPLE};
            }}
            QTabBar::tab:!selected {{
                margin-top: 2px;
            }}
        """)
        self.tab_widget.tabBar().setElideMode(Qt.ElideNone)
        self.tab_widget.tabBar().setExpanding(True)
        self.tab_widget.tabBar().setUsesScrollButtons(False)
        self.tab_widget.tabBar().setIconSize(self.tab_widget.tabBar().iconSize())
        self._build_tabs()
        layout.addWidget(self.tab_widget)

    def _build_tabs(self):
        self.wizard_tab = WizardConsoleTab()
        self.input_tab = InputManagementTab()
        self.cmd_editor_tab = CommandEditorTab()
        self.raw_output_tab = RawOutputTab()
        self.results_tab = ResultsDisplayTab()
        self.llm_tab = LLMModeTab()
        self.tool_selection_tab = ToolSelectionTab()

        self.tab_widget.addTab(self.wizard_tab, "Wizard Console")
        self.tab_widget.addTab(self.input_tab, "Input Management")
        self.tab_widget.addTab(self.cmd_editor_tab, "Command Editor")
        self.tab_widget.addTab(self.raw_output_tab, "Raw Output")
        self.tab_widget.addTab(self.results_tab, "Results Display")
        self.tab_widget.addTab(self.llm_tab, "LLM Mode")
        self.tab_widget.addTab(self.tool_selection_tab, "Tool Selection")
