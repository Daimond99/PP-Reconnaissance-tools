"""
Recon Tool - Main Window Module
หน้าต่างหลักของแอปพลิเคชัน
"""

from typing import List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QMenu,
)
from PySide6.QtCore import Qt, QRect, QEvent, QProcess
from PySide6.QtGui import QAction, QCursor, QKeySequence

from src.config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WARHEAD_COMMANDS, TOOL_COMMANDS,
)
from src.ui.widgets import Sidebar, TopBar, MainContentArea, svg_icon
from src.core.confirmation_gate import ConfirmationGate


class ReconMainWindow(QMainWindow):
    """หน้าต่างหลักของ Recon Tool"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        
        # Resize handling
        self.resize_margin = 10  # ขอบสำหรับ resize
        self.is_resizing = False
        self.resize_direction = None
        self.drag_start_pos = None
        self.drag_start_geometry = None
        
        # Drag handling
        self.dragPos = None
        
        self._build_menu()
        self._build_ui()
        self._connect_signals()

    def _build_menu(self):
        menubar = self.menuBar()

        self.new_scan_action = QAction("New Scan", self)
        self.stop_scan_action = QAction("Stop Scan", self)
        scan_menu = menubar.addMenu("Scan")
        scan_menu.addAction(self.new_scan_action)
        scan_menu.addAction(self.stop_scan_action)

        self.profile_mgmt_action = QAction("Profile Management", self)
        self.import_yaml_action = QAction("Import Profile (YAML)", self)
        self.export_mission_action = QAction("Export Current Mission", self)
        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction(self.profile_mgmt_action)
        tools_menu.addAction(self.import_yaml_action)
        tools_menu.addAction(self.export_mission_action)

        self.about_action = QAction("About", self)
        self.doc_action = QAction("Documentation", self)
        help_menu = menubar.addMenu("Help")
        help_menu.addAction(self.about_action)
        help_menu.addAction(self.doc_action)

    def _build_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.ArrowCursor)
        self.menuBar().hide()

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        central.installEventFilter(self)

        # Main Layout
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(0)

        # Title Bar
        self.title_bar = QFrame()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(42)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 6, 0)
        title_layout.setSpacing(2)

        # Plain, empty drag area — no brand mark, no title text (per mockup).
        drag_spacer = QLabel("")
        drag_spacer.setObjectName("TitleDragArea")

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(2)

        btn_min = QPushButton()
        btn_min.setObjectName("WinControlBtn")
        btn_min.setIcon(svg_icon("M5 12h14", color="#f8f8f2"))
        btn_min.setToolTip("Minimize")
        btn_min.clicked.connect(self.showMinimized)

        btn_max = QPushButton()
        btn_max.setObjectName("WinControlBtn")
        btn_max.setIcon(svg_icon("M5 5h14v14H5z", color="#f8f8f2"))
        btn_max.setToolTip("Maximize")
        btn_max.clicked.connect(self._toggle_maximize)

        btn_close = QPushButton()
        btn_close.setObjectName("WinControlCloseBtn")
        btn_close.setIcon(svg_icon("M6 6l12 12M18 6L6 18", color="#f8f8f2"))
        btn_close.setToolTip("Close")
        btn_close.clicked.connect(self.close)

        controls_layout.addWidget(btn_min)
        controls_layout.addWidget(btn_max)
        controls_layout.addWidget(btn_close)

        title_layout.addWidget(drag_spacer, 1)
        title_layout.addLayout(controls_layout)
        self._drag_widgets = (self.title_bar, drag_spacer)
        for widget in self._drag_widgets:
            widget.installEventFilter(self)

        root.addWidget(self.title_bar)

        # Menu Bar is handled by QMainWindow but we can style it
        # However, in design it's a separate div. Let's use the standard one
        # or create a custom one if needed. The design shows a dark bar.

        self.top_bar = TopBar()
        root.addWidget(self.top_bar)

        # Body
        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)

        self.sidebar = Sidebar()
        self.main_area = MainContentArea()
        body.addWidget(self.sidebar)

        vline = QFrame()
        vline.setObjectName("VLine")
        vline.setFixedWidth(1)
        body.addWidget(vline)

        content_card = QFrame()
        content_card.setObjectName("ContentCard")
        content_layout = QVBoxLayout(content_card)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.addWidget(self.main_area)
        body.addWidget(content_card, 1)
        root.addLayout(body, 1)

        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")
        status_bar.setFixedHeight(28)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(0, 0, 12, 0)
        dot = QLabel("●")
        dot.setObjectName("StatusDot")
        status_layout.addWidget(dot)
        status = QLabel("Ready — authorized targets only")
        status.setObjectName("StatusLabel")
        status_layout.addWidget(status)
        status_layout.addStretch()
        environment = QLabel("PySide6 • Local session")
        environment.setObjectName("StatusLabel")
        status_layout.addWidget(environment)
        status_bar.hide()
        root.addWidget(status_bar)

    def eventFilter(self, watched, event):
        """Make the frameless window drag and resize like a native window."""
        if event.type() not in (
            QEvent.MouseButtonPress, QEvent.MouseButtonDblClick,
            QEvent.MouseMove, QEvent.MouseButtonRelease,
        ):
            return super().eventFilter(watched, event)

        pos = watched.mapTo(self, event.position().toPoint())
        if event.type() == QEvent.MouseButtonDblClick and watched in self._drag_widgets:
            self._toggle_maximize()
            return True
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            direction = self._get_resize_direction(pos)
            if direction and not self.isMaximized():
                self.is_resizing = True
                self.resize_direction = direction
                self.drag_start_pos = event.globalPosition().toPoint()
                self.drag_start_geometry = QRect(self.geometry())
                return True
            if watched in self._drag_widgets:
                self.dragPos = event.globalPosition().toPoint()
                return True

        if event.type() == QEvent.MouseMove:
            self._update_cursor(pos)
            if event.buttons() & Qt.LeftButton:
                if self.is_resizing:
                    self._handle_resize(event.globalPosition().toPoint())
                    return True
                if self.dragPos is not None:
                    current = event.globalPosition().toPoint()
                    self.move(self.pos() + current - self.dragPos)
                    self.dragPos = current
                    return True

        if event.type() == QEvent.MouseButtonRelease:
            self.is_resizing = False
            self.resize_direction = None
            self.dragPos = None
            self.drag_start_pos = None
            self.drag_start_geometry = None
        return super().eventFilter(watched, event)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _get_resize_direction(self, pos):
        """กำหนดทิศทางการปรับขนาด"""
        if self.isMaximized():
            return None
            
        rect = self.rect()
        m = self.resize_margin
        width = rect.width()
        height = rect.height()
        
        # ตรวจสอบทุกมุมและขอบ
        on_left = pos.x() < m
        on_right = pos.x() > width - m
        on_top = pos.y() < m
        on_bottom = pos.y() > height - m
        
        # มุม (สำคัญกว่าขอบ)
        if on_top and on_left:
            return "top-left"
        elif on_top and on_right:
            return "top-right"
        elif on_bottom and on_left:
            return "bottom-left"
        elif on_bottom and on_right:
            return "bottom-right"
        # ขอบ
        elif on_top:
            return "top"
        elif on_bottom:
            return "bottom"
        elif on_left:
            return "left"
        elif on_right:
            return "right"
            
        return None

    def _update_cursor(self, pos):
        """อัปเดต cursor ตามทิศทางการปรับขนาด"""
        if self.isMaximized():
            self.setCursor(Qt.ArrowCursor)
            return
            
        direction = self._get_resize_direction(pos)
        cursor_map = {
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top-left": Qt.SizeFDiagCursor,
            "top-right": Qt.SizeBDiagCursor,
            "bottom-left": Qt.SizeBDiagCursor,
            "bottom-right": Qt.SizeFDiagCursor,
        }
        cursor = cursor_map.get(direction, Qt.ArrowCursor)
        self.setCursor(cursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            
            # ตรวจสอบว่าอยู่ใน title bar หรือไม่
            # title bar อยู่ที่ y = 6 ถึง 40 (เนื่องจากมี margin 6px)
            if 6 <= pos.y() <= 40:
                # Drag window
                self.dragPos = event.globalPos()
                self.is_resizing = False
                self._click_pos = pos
            else:
                # Check resize
                if not self.isMaximized():
                    direction = self._get_resize_direction(pos)
                    if direction:
                        self.is_resizing = True
                        self.resize_direction = direction
                        self.drag_start_pos = event.globalPos()
                        self.drag_start_geometry = QRect(self.geometry())
                        self.dragPos = None

    def mouseMoveEvent(self, event):
        # Update cursor ตลอดเวลาเมื่อไม่ได้ maximize
        if not self.isMaximized():
            self._update_cursor(event.pos())
        
        if event.buttons() == Qt.LeftButton:
            if self.is_resizing and self.resize_direction:
                self._handle_resize(event.globalPos())
                event.accept()
            elif self.dragPos is not None:
                # Drag window
                self.move(self.pos() + event.globalPos() - self.dragPos)
                self.dragPos = event.globalPos()
                event.accept()
    
    def enterEvent(self, event):
        """Update cursor when mouse enters window"""
        if not self.isMaximized():
            self._update_cursor(event.pos())
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Reset cursor when mouse leaves window"""
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        """Reset resize state"""
        self.is_resizing = False
        self.resize_direction = None
        self.dragPos = None
        self.drag_start_pos = None
        self.drag_start_geometry = None

    def _handle_resize(self, global_pos):
        """จัดการการปรับขนาดหน้าต่าง"""
        if not self.drag_start_pos or not self.drag_start_geometry:
            return
            
        delta = global_pos - self.drag_start_pos
        geometry = QRect(self.drag_start_geometry)
        min_width = self.minimumWidth()
        min_height = self.minimumHeight()
        
        direction = self.resize_direction
        
        # ปรับขนาดตามทิศทาง
        if "left" in direction:
            new_left = geometry.left() + delta.x()
            if geometry.right() - new_left >= min_width:
                geometry.setLeft(new_left)
            else:
                geometry.setLeft(geometry.right() - min_width)
        
        if "right" in direction:
            new_right = geometry.right() + delta.x()
            if new_right - geometry.left() >= min_width:
                geometry.setRight(new_right)
            else:
                geometry.setRight(geometry.left() + min_width)
        
        if "top" in direction:
            new_top = geometry.top() + delta.y()
            if geometry.bottom() - new_top >= min_height:
                geometry.setTop(new_top)
            else:
                geometry.setTop(geometry.bottom() - min_height)
        
        if "bottom" in direction:
            new_bottom = geometry.bottom() + delta.y()
            if new_bottom - geometry.top() >= min_height:
                geometry.setBottom(new_bottom)
            else:
                geometry.setBottom(geometry.top() + min_height)
        
        self.setGeometry(geometry)

    def _connect_signals(self):
        self.sidebar.navigate.connect(self._on_sidebar_navigation)
        self.sidebar.settings_btn.clicked.connect(self._on_settings_clicked)
        self.top_bar.opmode_combo.currentTextChanged.connect(self._on_opmode_change)
        self.top_bar.warhead_combo.currentTextChanged.connect(self._on_warhead_change)
        self.top_bar.tool_combo.currentTextChanged.connect(self._on_tool_change)
        self.top_bar.execute_btn.clicked.connect(self._on_execute_clicked)
        self.top_bar.command_input.returnPressed.connect(self._on_execute_clicked)

        self._top_bar_gate: ConfirmationGate | None = None
        self._top_bar_proc: QProcess | None = None

        self.new_scan_action.triggered.connect(self._on_new_scan)
        self.stop_scan_action.triggered.connect(self._on_stop_scan)
        self.profile_mgmt_action.triggered.connect(self._on_profile_management)
        self.import_yaml_action.triggered.connect(self._on_import_yaml)
        self.export_mission_action.triggered.connect(self._on_export_mission)
        self.about_action.triggered.connect(self._on_about)
        self.doc_action.triggered.connect(self._on_documentation)

        self._on_tool_change(self.top_bar.tool_combo.currentText())
        self._on_warhead_change(self.top_bar.warhead_combo.currentText())

    def _on_sidebar_navigation(self, index: int):
        self.main_area.stack.setCurrentIndex(index)

    def _on_settings_clicked(self):
        """Pop a File/Settings menu (Zenmap-style) at the Settings button."""
        menu = QMenu(self)
        entries = [
            ("New Window", "Ctrl+N", self._on_new_scan),
            ("Open Scan", "Ctrl+O", self._on_import_yaml),
            ("Open Scan in This Window", "", self._on_import_yaml),
            ("Save Scan", "Ctrl+S", self._on_export_mission),
            ("Save All Scans to Directory", "Ctrl+Alt+S", self._on_export_mission),
            (None, None, None),
            ("Close Window", "Ctrl+W", self.close),
            ("Quit", "Ctrl+Q", self.close),
        ]
        for label, shortcut, handler in entries:
            if label is None:
                menu.addSeparator()
                continue
            action = menu.addAction(label)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(handler)
        btn = self.sidebar.settings_btn
        menu.exec(btn.mapToGlobal(btn.rect().topRight()))

    def _on_opmode_change(self, mode):
        # Wizard Console page is a plain bash terminal now — both operation
        # modes just land on it, no separate wizard/direct-tool content to
        # switch between.
        self.main_area.stack.setCurrentIndex(0)

    def _get_target(self) -> str:
        return self.top_bar.target_text() or "192.168.1.0/24"

    def _apply_command_template(self, template: str) -> str:
        return template.replace("192.168.1.0/24", self._get_target()).replace(
            "192.168.1.1", self._get_target()
        )

    def _on_warhead_change(self, profile):
        template = WARHEAD_COMMANDS.get(profile, "")
        if template:
            self.top_bar.command_input.setText(self._apply_command_template(template))

    def _on_tool_change(self, tool):
        template = TOOL_COMMANDS.get(tool, "")
        if template:
            self.top_bar.command_input.setText(self._apply_command_template(template))

    def _on_execute_clicked(self):
        """Top-bar quick execute — validated + confirmed through
        ConfirmationGate before anything reaches QProcess, same as every
        other execution path in the app. Feedback goes through dialogs only —
        Raw Output / LLM Mode stay plain, unmodified bash terminals."""
        cmd = self.top_bar.command_input.text().strip()
        if not cmd:
            return

        # Record the executed target in the TARGET dropdown history.
        self.top_bar.add_target_history(self._get_target())

        gate = ConfirmationGate(channel="direct")
        result = gate.request(cmd, self._get_target())
        if not result.ok:
            QMessageBox.warning(self, "Command Rejected", result.message)
            return

        reply = QMessageBox.question(
            self, "Confirm Execution",
            f"{result.preview_box}\n\nRun this command exactly as previewed above?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            gate.cancel("user_declined")
            return

        gate.confirm("yes")
        self._run_gated_command(gate)

    def _run_gated_command(self, gate: ConfirmationGate):
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        output_chunks: List[str] = []

        def on_output():
            data = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
            if data:
                output_chunks.append(data)

        def on_finished(exit_code, _exit_status):
            gate.mark_executed_result(exit_code)
            self._top_bar_proc = None
            output = "".join(output_chunks)
            QMessageBox.information(
                self, "Execution Finished",
                f"Exit code {exit_code}\n\n{output[-2000:]}",
            )

        proc.readyReadStandardOutput.connect(on_output)
        proc.finished.connect(on_finished)
        argv = gate.argv
        self._top_bar_proc = proc
        proc.start(argv[0], argv[1:])

    def _on_new_scan(self):
        self._on_execute_clicked()

    def _on_stop_scan(self):
        if self._top_bar_proc and self._top_bar_proc.state() != QProcess.ProcessState.NotRunning:
            self._top_bar_proc.terminate()

    def _on_profile_management(self):
        pass

    def _on_import_yaml(self):
        pass

    def _on_export_mission(self):
        pass

    def _on_about(self):
        pass

    def _on_documentation(self):
        pass

    def closeEvent(self, event):
        if self._top_bar_proc and self._top_bar_proc.state() != QProcess.ProcessState.NotRunning:
            self._top_bar_proc.terminate()
        super().closeEvent(event)
