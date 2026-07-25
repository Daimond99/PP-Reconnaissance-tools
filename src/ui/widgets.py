"""
Recon Tool - Widgets Module
เก็บ UI components ทั้งหมด: Sidebar, TopBar, และ Tabs
"""

import platform
import subprocess
import threading

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QTextEdit, QTabWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
    QSizePolicy,
)
from PySide6.QtCore import Signal, QObject, Qt, QByteArray
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from src.config import (
    TERMINAL_FONT_FAMILY, TERMINAL_FONT_SIZE,
    TOOL_LIST, WARHEAD_PROFILES, OPERATION_MODES,
    DIRECT_TOOL_CONTENT, LLM_DEMO_TEXT,
    BG, PANEL_LIGHT, PURPLE, TEXT, TEXT_DIM, BORDER, CONSOLE_BG, CONSOLE_TEXT,
)

from src.core.wizard_engine import WizardEngine
from src.core.tool_manager import get_tool_manager
from src.ui.llm_mode import LLMModeTab
from src.ui.tool_selection import ToolSelectionTab


# ============================================================================
# SIGNALS - สำหรับ thread-safe output
# ============================================================================

class TerminalSignals(QObject):
    """Signal สำหรับ thread-safe output"""
    output = Signal(str)


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

class WizardConsoleTab(QWidget):
    """Tab สำหรับ Wizard Console - Hydra-style interactive interface"""
    
    commandEntered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize wizard engine and tool manager
        self.wizard_engine = WizardEngine()
        self.tool_manager = get_tool_manager()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = QFont(TERMINAL_FONT_FAMILY, 11)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(False) # เปลี่ยนเป็น False เพื่อให้พิมพ์ได้
        self.output_area.setAcceptRichText(True)  # Enable rich text for colors
        self.output_area.setFont(font)
        self.output_area.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; border-radius: 4px; padding: 30px 35px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
            line-height: 150%;
        """)
        layout.addWidget(self.output_area, 1)
        self.console = self.output_area

        # self.input_line และ layout ที่เกี่ยวข้องถูกนำออกตามคำขอ
        self._history = []
        self._history_index = -1
        
        # เชื่อมต่อ keyPressEvent เพื่อจัดการการพิมพ์ใน terminal
        self.output_area.keyPressEvent = self._make_key_handler(self.output_area.keyPressEvent)
        
        # Show initial wizard content
        self._show_initial_menu()

    def _make_key_handler(self, original_handler):
        def handler(event):
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                # ดึงบรรทัดสุดท้ายมาเป็นคำสั่ง
                cursor = self.output_area.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.select(cursor.SelectionType.LineUnderCursor)
                line = cursor.selectedText()
                
                # หาตำแหน่ง prompt ล่าสุด (เช่น "Select>" หรือ ">")
                if ">" in line:
                    cmd = line.split(">")[-1].strip()
                else:
                    cmd = line.strip()

                if cmd:
                    # Echo the input clearly (optional, since user already typed it, but good for logic)
                    # self._append_colored(f"\n", "#ffffff") # Just a newline
                    self._on_command_entered(cmd)
                return
            
            # ป้องกันการลบเนื้อหาเก่า (ReadOnly-ish behavior for previous lines)
            if event.key() == Qt.Key_Backspace or event.key() == Qt.Key_Left:
                cursor = self.output_area.textCursor()
                # ถ้า cursor อยู่ต้นบรรทัดที่มี prompt ไม่ให้ลบ
                line_text = cursor.block().text()
                col = cursor.positionInBlock()
                if ">" in line_text:
                    prompt_pos = line_text.find(">") + 1
                    if col <= prompt_pos:
                        return

            original_handler(event)
        return handler

    def _on_command_entered(self, text):
        if not text:
            return

        # Add to history
        self._history.append(text)
        self._history_index = len(self._history)

        # WizardEngine.handle_input() already understands the meta-commands
        # check / install / help / reset / back / cancel internally — just
        # forward everything to it and render the result.
        is_meta_info = text.strip().lower() in ("check", "install", "help")
        result = self.wizard_engine.handle_input(text)
        self._render_result(result, clear=not is_meta_info)
    
    def _show_initial_menu(self):
        """แสดงเมนูเริ่มต้น (TOOL_SELECT) จาก wizard engine จริง"""
        result = self.wizard_engine.reset()
        self._render_result(result, clear=True)
    
    def _clear_output(self):
        """ล้าง output area"""
        self.output_area.clear()
    
    def _append_output(self, text: str):
        """เพิ่ม text ธรรมดา"""
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()
    
    def _append_colored(self, text: str, color: str):
        """เพิ่ม text สี"""
        color = CONSOLE_TEXT
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()
    
    def _render_result(self, result, clear: bool = True):
        """
        Render a WizardResult(success, lines, prompt, action, commands) —
        the actual return type of WizardEngine.handle_input()/reset()/go_back().
        """
        if clear:
            self._clear_output()

        handled_sentinel = False
        for line in result.lines:
            if line == "__SHOW_TOOL_STATUS__":
                self._show_tool_status()
                handled_sentinel = True
                continue
            if line == "__SHOW_INSTALL_GUIDE__":
                self._show_install_guide()
                handled_sentinel = True
                continue
            self._append_output(line + "\n")

        if handled_sentinel:
            return  # _show_tool_status()/_show_install_guide() already end with a prompt

        if result.action == "execute":
            for cmd in (result.commands or []):
                self.commandEntered.emit(cmd)
            self._append_output("Use 'reset' to start a new wizard session.\n\n")
            self._append_colored("Select>", "#00ff88")
            return

        if result.action == "cancel":
            self._append_colored("\nSelect>", "#00ff88")
            return

        prompt_text = result.prompt or "Select>"
        self._append_colored(f"\n{prompt_text}", "#00ff88")

        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)
    
    def _on_return_pressed(self):
        # This method is no longer used but kept to avoid breaking references if any
        pass
    
    def _show_tool_status(self):
        """แสดงสถานะของ tools"""
        self._append_output("\n")
        for tool_name, (installed, status) in self.tool_manager.get_all_status().items():
            color = "#00ff00" if installed else "#ff6666"
            self._append_colored(f"{status}\n", color)
        self._append_colored("\nSelect> ", "#00ff88")
    
    def _show_install_guide(self):
        """แสดงคำแนะนำการติดตั้ง"""
        missing = self.tool_manager.get_missing_tools()
        if not missing:
            self._append_colored("\nAll tools are installed!\n", "#00ff00")
            self._append_colored("\nSelect> ", "#00ff88")
            return
        
        self._append_output("\n")
        for tool_name in missing:
            guide = self.tool_manager.get_install_guide(tool_name)
            tool_info = self.tool_manager.get_tool_info(tool_name)
            self._append_colored(f"\n{tool_info.display_name}:\n", "#ffff00")
            for line in guide.split('\n'):
                self._append_colored(f"  {line}\n", "#aaaaaa")
        
        self._append_colored("\nSelect> ", "#00ff88")
    
    def write_output(self, text: str):
        """เขียน output ไปยัง console"""
        self._append_output(text)


class RawOutputTab(QWidget):
    """Tab สำหรับ Raw Output Console - พิมพ์คำสั่งตรง terminal ได้เลย"""
    
    commandEntered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = QFont(TERMINAL_FONT_FAMILY, 11)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(False)
        self.output_area.setAcceptRichText(False)
        self.output_area.setFont(font)
        self.output_area.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; border-radius: 4px; padding: 20px 24px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
        """)
        layout.addWidget(self.output_area, 1)
        self.console = self.output_area

        self._proc = None
        self._history = []
        self._history_index = -1
        self._signals = TerminalSignals()
        self._signals.output.connect(self._append_output)
        self._is_windows = platform.system() == "Windows"
        
        # Bind Enter key on output_area to send command
        self.output_area.keyPressEvent = self._make_key_handler(self.output_area.keyPressEvent)
        
        self._start_shell()
    
    def _make_key_handler(self, original_handler):
        def handler(event):
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                # Extract last line as command
                cursor = self.output_area.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.select(cursor.SelectionType.LineUnderCursor)
                last_line = cursor.selectedText().strip()
                if last_line:
                    self._send_to_shell(last_line)
                    self.commandEntered.emit(last_line)
            else:
                original_handler(event)
        return handler
    
    def _send_to_shell(self, cmd: str):
        """ส่งคำสั่งไปยัง shell"""
        if self._proc and self._proc.poll() is None:
            self.output_area.append(f"\n$ {cmd}")
            self._proc.stdin.write(cmd + "\n")
            self._proc.stdin.flush()

    def _start_shell(self):
        """Start shell process (PowerShell on Windows, bash on Linux)"""
        try:
            if self._is_windows:
                self._proc = subprocess.Popen(
                    ["powershell.exe", "-NoLogo", "-NoExit", "-Command", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self._proc = subprocess.Popen(
                    ["bash", "-i"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

            def read_stdout():
                try:
                    for line in iter(self._proc.stdout.readline, ""):
                        if line:
                            self._signals.output.emit(line.rstrip("\n\r"))
                except Exception:
                    pass

            threading.Thread(target=read_stdout, daemon=True).start()
        except Exception as e:
            self._append_output(f"Error starting shell: {e}")

    def _append_output(self, text: str):
        self.output_area.append(text)
        scrollbar = self.output_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def write_command(self, cmd: str):
        if self._proc and self._proc.poll() is None:
            self._append_output(f"$ {cmd}")
            self._proc.stdin.write(cmd + "\n")
            self._proc.stdin.flush()
        else:
            self._append_output(f"Shell not available. Command: {cmd}")

    def closeEvent(self, event):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        super().closeEvent(event)


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
