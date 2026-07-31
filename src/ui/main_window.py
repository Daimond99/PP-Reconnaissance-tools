"""
Recon Tool - Main Window Module
หน้าต่างหลักของแอปพลิเคชัน
"""

import os
import shlex
import uuid

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QMenu, QFileDialog,
)
from PySide6.QtCore import Qt, QRect, QEvent
from PySide6.QtGui import QAction, QKeySequence

from src.config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WARHEAD_COMMANDS, TOOL_COMMANDS,
)
from src.ui.widgets import Sidebar, TopBar, MainContentArea, InputManagementTab, svg_icon
from src.core.confirmation_gate import ConfirmationGate
from src.tools.nmap.parser import parse_nmap_xml


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
        # The QMainWindow menu bar is hidden — all actions live in the
        # title-bar Settings dropdown. These QActions are kept only so their
        # keyboard shortcuts stay live app-wide.
        self.new_scan_action = QAction("New Scan", self)
        self.new_scan_action.setShortcut(QKeySequence("Ctrl+N"))
        self.open_scan_action = QAction("Open Scan", self)
        self.open_scan_action.setShortcut(QKeySequence("Ctrl+O"))
        self.save_scan_action = QAction("Save Scan", self)
        self.save_scan_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_all_action = QAction("Save All Scans", self)
        self.save_all_action.setShortcut(QKeySequence("Ctrl+Alt+S"))
        for action in (self.new_scan_action, self.open_scan_action,
                       self.save_scan_action, self.save_all_action):
            self.addAction(action)

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

        # Left cluster: sidebar collapse/expand toggle + Settings dropdown.
        left_controls = QHBoxLayout()
        left_controls.setSpacing(2)

        self.sidebar_toggle_btn = QPushButton()
        self.sidebar_toggle_btn.setObjectName("TitleToolBtn")
        self.sidebar_toggle_btn.setIcon(svg_icon("M4 6h16M4 12h16M4 18h16", color="#b8b8c4"))
        self.sidebar_toggle_btn.setToolTip("Collapse / expand sidebar")
        self.sidebar_toggle_btn.setCursor(Qt.PointingHandCursor)

        self.settings_btn = QPushButton("  Settings  ▾")
        self.settings_btn.setObjectName("TitleSettingsBtn")
        self.settings_btn.setCursor(Qt.PointingHandCursor)

        left_controls.addWidget(self.sidebar_toggle_btn)
        left_controls.addWidget(self.settings_btn)

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

        title_layout.addLayout(left_controls)
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

        self.sidebar_vline = QFrame()
        self.sidebar_vline.setObjectName("VLine")
        self.sidebar_vline.setFixedWidth(1)
        body.addWidget(self.sidebar_vline)

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
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        self.top_bar.opmode_combo.currentTextChanged.connect(self._on_opmode_change)
        self.top_bar.warhead_combo.currentTextChanged.connect(self._on_warhead_change)
        self.top_bar.tool_combo.currentTextChanged.connect(self._on_tool_change)
        self.top_bar.execute_btn.clicked.connect(self._on_execute_clicked)
        self.top_bar.command_input.returnPressed.connect(self._on_execute_clicked)
        self.top_bar.target_input.editTextChanged.connect(self._on_target_changed)
        self._last_target = self._get_target()

        input_tab = self.main_area.input_tab
        input_tab.reuseRequested.connect(self.top_bar.command_input.setText)
        input_tab.cancelRequested.connect(self._on_queue_cancel)

        # RawOutputTab.commandDone is a stable signal owned by the tab
        # itself (not the lazily-spawned inner terminal) — safe to connect
        # here regardless of whether the real terminal has been created yet.
        self.main_area.raw_output_tab.commandDone.connect(self._on_direct_command_done)

        # token -> (ConfirmationGate, queue row), for the async completion
        # signal from the Raw Output terminal (Direct Tool Mode Execute).
        self._pending_direct_scans: dict = {}

        self.new_scan_action.triggered.connect(self._on_new_scan)
        self.open_scan_action.triggered.connect(self._on_open_scan)
        self.save_scan_action.triggered.connect(self._on_save_scan)
        self.save_all_action.triggered.connect(self._on_save_all_scans)

        self._on_tool_change(self.top_bar.tool_combo.currentText())
        self._on_warhead_change(self.top_bar.warhead_combo.currentText())

    # Sidebar index of the Raw Output page (see Sidebar.NAV_ITEMS).
    RAW_OUTPUT_INDEX = 2

    def _toggle_sidebar(self):
        """Fully hide/show the sidebar (and its divider), Claude Code
        desktop-style — the main content reclaims the full width."""
        self._sidebar_hidden = not getattr(self, "_sidebar_hidden", False)
        self.sidebar.setVisible(not self._sidebar_hidden)
        self.sidebar_vline.setVisible(not self._sidebar_hidden)

    def _on_sidebar_navigation(self, index: int):
        self.main_area.stack.setCurrentIndex(index)
        if index == self.RAW_OUTPUT_INDEX:
            self.main_area.raw_output_tab.focus()

    def _on_settings_clicked(self):
        """Pop the Settings menu below the title-bar button. Only actions the
        app can actually perform — Zenmap-style scan file management + run."""
        menu = QMenu(self)
        entries = [
            ("New Scan", "Ctrl+N", self._on_new_scan),
            ("Stop Scan", "", self._on_stop_scan),
            (None, None, None),
            ("Open Scan…", "Ctrl+O", self._on_open_scan),
            ("Save Scan…", "Ctrl+S", self._on_save_scan),
            ("Save All Scans…", "Ctrl+Alt+S", self._on_save_all_scans),
            (None, None, None),
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
        btn = self.settings_btn
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

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
            self._last_target = self._get_target()

    def _on_tool_change(self, tool):
        template = TOOL_COMMANDS.get(tool, "")
        if template:
            self.top_bar.command_input.setText(self._apply_command_template(template))
            self._last_target = self._get_target()

    def _on_target_changed(self, text: str) -> None:
        """Typing a new TARGET live-updates the command box — swaps whatever
        target substring is currently in there for the new one, so the user
        just types their own IP and the command follows along."""
        text = text.strip()
        if not text or text == self._last_target:
            return
        current = self.top_bar.command_input.text()
        if self._last_target and self._last_target in current:
            self.top_bar.command_input.setText(current.replace(self._last_target, text))
        self._last_target = text

    def _on_execute_clicked(self):
        """Top-bar Direct Tool Mode Execute — validated + confirmed through
        ConfirmationGate, same as every other execution path, then run in
        the Raw Output terminal (same xterm.js backend as the Wizard
        Console) so real color/output show live, and queued in the Input
        Management scan-history table."""
        cmd = self.top_bar.command_input.text().strip()
        if not cmd:
            return

        # Record the executed target in the TARGET dropdown history.
        self.top_bar.add_target_history(self._get_target())

        # If this is a plain nmap invocation with no output-format flag of
        # its own, tack on `-oX <file>` so Results Display can be populated
        # with real structured data once the scan finishes. This happens
        # BEFORE gate.request() so the confirmation preview shows the exact
        # command that will run — nothing hidden from the "yes" prompt.
        xml_paths = self._nmap_xml_capture_paths(cmd)
        if xml_paths:
            cmd = f"{cmd} -oX {xml_paths[0]}"

        gate = ConfirmationGate(channel="direct")
        # Direct Tool Mode targets are whatever the user typed into TARGET
        # themselves (their own lab/VM) — no AUTHORIZED_SCOPE block here.
        result = gate.request(cmd, self._get_target(), skip_scope=True)
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
        self._run_direct_command(gate, xml_paths)

    def _nmap_xml_capture_paths(self, cmd: str) -> tuple[str, str] | None:
        """If `cmd` is a bare `nmap ...` invocation with no `-oX`/`-oA`/`-oN`/
        `-oG` of its own, return (shell_path, host_path) for a fresh scratch
        XML file: `shell_path` is the path as seen inside the shell the
        command actually runs in (WSL Ubuntu bash on Windows, native bash on
        Linux), `host_path` is how this (Windows-native) Python process reads
        that same file back afterward. Returns None for anything else —
        masscan/hydra/ncrack/ncat/evil-winrm, or a command with its own -o*
        flag, are left untouched."""
        try:
            tokens = shlex.split(cmd)
        except ValueError:
            return None
        if not tokens:
            return None
        if os.path.basename(tokens[0]).lower() == "sudo":
            tokens = tokens[1:]
        if not tokens or os.path.basename(tokens[0]).lower() not in ("nmap", "nmap.exe"):
            return None
        if any(tok in ("-oX", "-oA", "-oN", "-oG", "-oS") for tok in tokens[1:]):
            return None

        shell_path = f"/tmp/therecon_scan_{uuid.uuid4().hex[:8]}.xml"
        if os.name == "nt":
            host_path = "\\\\wsl$\\Ubuntu" + shell_path.replace("/", "\\")
        else:
            host_path = shell_path
        return shell_path, host_path

    def _run_direct_command(self, gate: ConfirmationGate,
                             xml_paths: tuple[str, str] | None = None) -> None:
        row = self.main_area.input_tab.add_entry(gate.command, status="Running")

        # Jump the view to Raw Output so the scan is visible immediately, and
        # give the terminal real keyboard focus so Ctrl+C interrupts it.
        self.sidebar.select_index(self.RAW_OUTPUT_INDEX)
        self.main_area.stack.setCurrentIndex(self.RAW_OUTPUT_INDEX)
        self.main_area.raw_output_tab.focus()

        token = self.main_area.raw_output_tab.run_command(shlex.join(gate.argv))
        if token:
            self._pending_direct_scans[token] = (gate, row, xml_paths)
        else:
            # Backend can't report completion (legacy fallback) — best effort.
            gate.mark_executed_result(0)
            self.main_area.input_tab.set_status(row, "Done")

    def _on_direct_command_done(self, token: str, exit_code: int) -> None:
        pending = self._pending_direct_scans.pop(token, None)
        if not pending:
            return
        gate, row, xml_paths = pending
        gate.mark_executed_result(exit_code)
        self.main_area.input_tab.set_status(row, "Done" if exit_code == 0 else "Error")
        if exit_code == 0 and xml_paths:
            self._ingest_nmap_xml(xml_paths[1])

    def _ingest_nmap_xml(self, host_path: str) -> None:
        """Parse the scratch `-oX` file a completed Direct Tool Mode nmap
        scan wrote and feed it into Results Display. Best-effort — a WSL
        distro named something other than "Ubuntu", or the file not showing
        up yet on the `\\\\wsl$` share, just means Results Display stays as
        it was; the scan itself already succeeded and is visible in Raw
        Output regardless."""
        hosts = parse_nmap_xml(host_path)
        if hosts:
            self.main_area.results_tab.merge_hosts(hosts)
        try:
            os.remove(host_path)
        except OSError:
            pass

    def _on_queue_cancel(self, _row: int) -> None:
        # One shared Raw Output terminal — Cancel Scan interrupts whatever
        # is currently running there (Ctrl+C).
        self.main_area.raw_output_tab.interrupt()

    def _on_new_scan(self):
        self._on_execute_clicked()

    def _on_stop_scan(self):
        self.main_area.raw_output_tab.interrupt()

    # -- scan file management (Settings ▸ Open/Save) -----------------------
    def _on_open_scan(self):
        """Open a saved scan XML: repopulate the command box + TARGET field,
        and add it back into the Input Management history table."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Scan", "", "Nmap XML (*.xml)"
        )
        if not path:
            return
        command = InputManagementTab._parse_nmap_xml_command(path)
        if not command:
            QMessageBox.warning(
                self, "Open Scan", "Could not read a command from that XML file."
            )
            return
        tokens = command.split()
        target = tokens[-1] if tokens else ""
        if target:
            self.top_bar.add_target_history(target)
            self._last_target = target
        self.top_bar.command_input.setText(command)
        self.main_area.input_tab.add_entry(command, status="Loaded", xml_path=path)

    def _on_save_scan(self):
        """Save the scan selected in Input Management as an XML file."""
        command = self.main_area.input_tab.selected_command()
        if not command:
            QMessageBox.information(
                self, "Save Scan",
                "Select a scan in Input Management first.",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Scan", "scan.xml", "Nmap XML (*.xml)"
        )
        if not path:
            return
        if self._write_scan_xml(command, path):
            self.main_area.input_tab.add_entry(command, status="Loaded", xml_path=path)

    def _on_save_all_scans(self):
        """Save every scan in Input Management to a chosen directory."""
        commands = self.main_area.input_tab.all_commands()
        if not commands:
            QMessageBox.information(
                self, "Save All Scans", "No scans in Input Management to save."
            )
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Save All Scans to Directory"
        )
        if not directory:
            return
        saved = 0
        for i, command in enumerate(commands, 1):
            if self._write_scan_xml(command, os.path.join(directory, f"scan_{i}.xml")):
                saved += 1
        QMessageBox.information(
            self, "Save All Scans", f"Saved {saved} scan(s) to:\n{directory}"
        )

    def _write_scan_xml(self, command: str, path: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(InputManagementTab.build_scan_xml(command))
            return True
        except OSError as exc:
            QMessageBox.warning(self, "Save Scan", f"Could not write file:\n{exc}")
            return False

    def closeEvent(self, event):
        stop = getattr(self.main_area.wizard_tab, "stop_all", None)
        if callable(stop):
            stop()
        for term in (self.main_area.raw_output_tab.terminal, self.main_area.llm_tab):
            stop = getattr(term, "stop", None)
            if callable(stop):
                stop()
        super().closeEvent(event)
