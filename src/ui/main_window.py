"""
Recon Tool - Main Window Module
หน้าต่างหลักของแอปพลิเคชัน
"""

import os
import shlex
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QMenu, QFileDialog, QSplitter,
)
from PySide6.QtCore import Qt, QRect, QEvent, QTimer
from PySide6.QtGui import QAction, QKeySequence

from src.config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WARHEAD_COMMANDS, TOOL_COMMANDS,
)
from src.ui.widgets import Sidebar, TopBar, MainContentArea, InputManagementTab, svg_icon
from src.core.confirmation_gate import ConfirmationGate
from src.tools.nmap.parser import parse_nmap_xml
from src.tools.hydra.parser import parse_hydra_output
from src.tools.ncrack.parser import parse_ncrack_output


@dataclass
class _PendingDirectScan:
    """One in-flight Direct Tool Mode Execute run, tracked from the moment
    the Raw Output terminal starts it until its `commandDone` fires."""
    gate: ConfirmationGate
    row: int
    # (kind, shell_path, host_path) or None. kind is "scan" (nmap/masscan
    # -oX, parsed by parse_nmap_xml) or "hydra"/"ncrack" (their own found-
    # credentials output, parsed into Results Display's Credentials Found
    # view).
    capture: Optional[Tuple[str, str, str]]


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

        # Body — a QSplitter so the sidebar can be drag-resized VS
        # Code-style; the handle itself is the divider (styled to a thin
        # line, same as the old static #VLine it replaces).
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setObjectName("BodySplitter")
        body.setContentsMargins(12, 12, 12, 12)
        body.setHandleWidth(9)
        body.setChildrenCollapsible(False)

        self.sidebar = Sidebar()
        self.main_area = MainContentArea()
        body.addWidget(self.sidebar)

        content_card = QFrame()
        content_card.setObjectName("ContentCard")
        content_layout = QVBoxLayout(content_card)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.addWidget(self.main_area)
        body.addWidget(content_card)

        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setSizes([220, max(WINDOW_WIDTH - 220, 400)])
        root.addWidget(body, 1)

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

    def leaveEvent(self, event):
        """Reset cursor when mouse leaves window"""
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

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
        self.top_bar.target_input.textChanged.connect(self._on_target_changed)
        self._last_target = self._get_target()

        input_tab = self.main_area.input_tab
        input_tab.reuseRequested.connect(self.top_bar.command_input.setText)
        input_tab.cancelRequested.connect(self._on_queue_cancel)

        # RawOutputTab.commandDone is a stable signal owned by the tab
        # itself (not the lazily-spawned inner terminal) — safe to connect
        # here regardless of whether the real terminal has been created yet.
        self.main_area.raw_output_tab.commandDone.connect(self._on_direct_command_done)

        # run_command() token -> _PendingDirectScan, for the async completion
        # signal from the Raw Output terminal (Direct Tool Mode Execute).
        self._pending_direct_scans: dict[str, _PendingDirectScan] = {}

        self.new_scan_action.triggered.connect(self._on_new_scan)
        self.open_scan_action.triggered.connect(self._on_open_scan)
        self.save_scan_action.triggered.connect(self._on_save_scan)
        self.save_all_action.triggered.connect(self._on_save_all_scans)

        self._on_tool_change(self.top_bar.tool_combo.currentText())
        self._on_warhead_change(self.top_bar.warhead_combo.currentText())
        self._on_opmode_change(self.top_bar.opmode_combo.currentText())

    # Sidebar index of the Raw Output page (see Sidebar.NAV_ITEMS).
    RAW_OUTPUT_INDEX = 2

    def _toggle_sidebar(self):
        """Fully hide/show the sidebar, Claude Code desktop-style — the
        main content reclaims the full width. The splitter handle hides
        along with it automatically (Qt ties a handle's visibility to the
        pane it precedes)."""
        self._sidebar_hidden = not getattr(self, "_sidebar_hidden", False)
        self.sidebar.setVisible(not self._sidebar_hidden)

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

    # Sidebar index of the Wizard Console page (see Sidebar.NAV_ITEMS).
    WIZARD_CONSOLE_INDEX = 0

    def _on_opmode_change(self, mode):
        """OPERATION MODE gates the command box + Execute button: picking
        "Wizard Mode" jumps to the Wizard Console page; picking "Direct Tool
        Mode" unlocks typing a command and running it; the placeholder
        ("Select Mode…", or anything else) leaves both locked."""
        if mode == "Wizard Mode":
            self.sidebar.select_index(self.WIZARD_CONSOLE_INDEX)
            self.main_area.stack.setCurrentIndex(self.WIZARD_CONSOLE_INDEX)
            self.top_bar.command_input.setEnabled(False)
            self.top_bar.execute_btn.setEnabled(False)
        elif mode == "Direct Tool Mode":
            self.top_bar.command_input.setEnabled(True)
            self.top_bar.execute_btn.setEnabled(True)
        else:
            self.top_bar.command_input.setEnabled(False)
            self.top_bar.execute_btn.setEnabled(False)

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
        self.top_bar.set_warhead_profiles(tool)
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
        # Guards the "New Scan" menu action / Ctrl+N too, not just the
        # Execute button itself — both reach this method directly.
        if self.top_bar.opmode_combo.currentText() != "Direct Tool Mode":
            return
        cmd = self.top_bar.command_input.text().strip()
        if not cmd:
            return

        # If this is a plain nmap/masscan invocation with no output-format
        # flag of its own, tack on `-oX <file>` so Results Display can be
        # populated with real structured data once the scan finishes — both
        # tools' -oX schema is close enough (host/address/ports/port) that
        # the same generic parser reads either one. Same idea for a bare
        # hydra/ncrack invocation, feeding their found-credentials output
        # into Results Display's Credentials Found view instead. All of
        # this happens BEFORE gate.request() so the confirmation preview
        # shows the exact command that will run — nothing hidden from the
        # "yes" prompt.
        capture: Optional[Tuple[str, str, str]] = None
        xml_paths = self._scan_xml_capture_paths(cmd)
        if xml_paths:
            cmd = f"{cmd} -oX {xml_paths[0]}"
            capture = ("scan", xml_paths[0], xml_paths[1])
        else:
            cred_paths = self._cred_capture_paths(cmd)
            if cred_paths:
                tool, shell_path, host_path = cred_paths
                flag = "-o" if tool == "hydra" else "-oN"
                cmd = f"{cmd} {flag} {shell_path}"
                capture = (tool, shell_path, host_path)

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
        self._run_direct_command(gate, capture)

    # Both tools' own output-format flags — if the user already asked for
    # one of these, don't tack on a second -oX (nmap: -oX/-oA/-oN/-oG/-oS;
    # masscan: -oX/-oJ/-oL/-oG/-oD/-oB).
    _SCAN_OUTPUT_FLAGS = {"-oX", "-oA", "-oN", "-oG", "-oS", "-oJ", "-oL", "-oD", "-oB"}

    def _scan_xml_capture_paths(self, cmd: str) -> tuple[str, str] | None:
        """If `cmd` is a bare `nmap ...`/`masscan ...` invocation (optionally
        `sudo`-prefixed) with no output-format flag of its own, return
        (shell_path, host_path) for a fresh scratch XML file: `shell_path`
        is the path as seen inside the shell the command actually runs in
        (WSL Ubuntu bash on Windows, native bash on Linux), `host_path` is
        how this (Windows-native) Python process reads that same file back
        afterward. Returns None for anything else — hydra/ncrack/ncat/
        evil-winrm, or a command with its own -o* flag, are left
        untouched."""
        try:
            tokens = shlex.split(cmd)
        except ValueError:
            return None
        if not tokens:
            return None
        if os.path.basename(tokens[0]).lower() == "sudo":
            tokens = tokens[1:]
        if not tokens or os.path.basename(tokens[0]).lower() not in (
            "nmap", "nmap.exe", "masscan", "masscan.exe",
        ):
            return None
        if any(tok in self._SCAN_OUTPUT_FLAGS for tok in tokens[1:]):
            return None

        shell_path = f"/tmp/therecon_scan_{uuid.uuid4().hex[:8]}.xml"
        if os.name == "nt":
            host_path = "\\\\wsl$\\Ubuntu" + shell_path.replace("/", "\\")
        else:
            host_path = shell_path
        return shell_path, host_path

    # Output flags that already give hydra/ncrack found-credentials output
    # of their own — don't tack on a second one.
    _CRED_OUTPUT_FLAGS = {
        "hydra": {"-o", "-oJ"},
        "ncrack": {"-oN", "-oX", "-oG", "-oA"},
    }

    def _cred_capture_paths(self, cmd: str) -> tuple[str, str, str] | None:
        """If `cmd` is a bare `hydra ...`/`ncrack ...` invocation (optionally
        `sudo`-prefixed) with no output flag of its own, return
        (tool, shell_path, host_path) for a fresh scratch output file:
        hydra's own `-o` (plain found-credentials text) or ncrack's `-oN`
        (Normal format, also lists discovered credentials). Returns None
        for anything else."""
        try:
            tokens = shlex.split(cmd)
        except ValueError:
            return None
        if not tokens:
            return None
        if os.path.basename(tokens[0]).lower() == "sudo":
            tokens = tokens[1:]
        if not tokens:
            return None

        program = os.path.basename(tokens[0]).lower()
        tool = {
            "hydra": "hydra", "hydra.exe": "hydra",
            "ncrack": "ncrack", "ncrack.exe": "ncrack",
        }.get(program)
        if tool is None:
            return None
        if any(tok in self._CRED_OUTPUT_FLAGS[tool] for tok in tokens[1:]):
            return None

        shell_path = f"/tmp/therecon_{tool}_{uuid.uuid4().hex[:8]}.txt"
        if os.name == "nt":
            host_path = "\\\\wsl$\\Ubuntu" + shell_path.replace("/", "\\")
        else:
            host_path = shell_path
        return tool, shell_path, host_path

    def _run_direct_command(self, gate: ConfirmationGate,
                             capture: tuple[str, str, str] | None = None) -> None:
        row = self.main_area.input_tab.add_entry(gate.command, status="Running")

        # Jump the view to Raw Output so the scan is visible immediately, and
        # give the terminal real keyboard focus so Ctrl+C interrupts it.
        self.sidebar.select_index(self.RAW_OUTPUT_INDEX)
        self.main_area.stack.setCurrentIndex(self.RAW_OUTPUT_INDEX)
        self.main_area.raw_output_tab.focus()

        token = self.main_area.raw_output_tab.run_command(shlex.join(gate.argv))
        if token:
            self._pending_direct_scans[token] = _PendingDirectScan(gate, row, capture)
        else:
            # Backend can't report completion (legacy fallback) — best effort.
            gate.mark_executed_result(0)
            self.main_area.input_tab.set_status(row, "Done")

    # How long \\wsl$ can lag showing a file the WSL side just finished
    # writing, observed in practice: the first read right after exit_code
    # arrives can legitimately come up empty even though the scan worked.
    _XML_READ_RETRIES = 6
    _XML_READ_RETRY_MS = 300

    def _on_direct_command_done(self, token: str, exit_code: int) -> None:
        pending = self._pending_direct_scans.pop(token, None)
        if not pending:
            return
        pending.gate.mark_executed_result(exit_code)
        self.main_area.input_tab.set_status(pending.row, "Done" if exit_code == 0 else "Error")
        if exit_code == 0 and pending.capture:
            kind, _shell_path, host_path = pending.capture
            if kind == "scan":
                self._ingest_nmap_xml(host_path, self._XML_READ_RETRIES)
            else:
                self._ingest_credentials(kind, host_path, pending.gate.target, self._XML_READ_RETRIES)

    def _ingest_nmap_xml(self, host_path: str, retries_left: int) -> None:
        """Parse the scratch `-oX` file a completed Direct Tool Mode
        nmap/masscan scan wrote and feed it into Results Display —
        `parse_nmap_xml` doesn't actually check `scanner=`, it just walks
        `<host>`/`<address>`/`<ports>`/`<port>` elements, and masscan's -oX
        schema is a compatible subset of nmap's, so one parser covers both.
        Comes back empty both on a genuine parse failure AND on the file
        simply not existing yet from this (Windows-native) process's point
        of view — the two look identical, so on empty we retry a few times
        on a timer instead of giving up on the first miss. A WSL distro
        named something other than "Ubuntu" still degrades to "no update",
        same as before."""
        hosts = parse_nmap_xml(host_path)
        if hosts:
            # Every scan gets its own row, even a repeat of the same IP with
            # different flags — label it with the time so duplicate-IP rows
            # are still tellable apart in the host list.
            stamp = datetime.now().strftime("%H:%M:%S")
            for host in hosts:
                host["label"] = f"{host['host']} · {stamp}"
            self.main_area.results_tab.add_scan_results(hosts)
            try:
                os.remove(host_path)
            except OSError:
                pass
            return
        if retries_left > 0:
            QTimer.singleShot(
                self._XML_READ_RETRY_MS,
                lambda: self._ingest_nmap_xml(host_path, retries_left - 1),
            )

    def _ingest_credentials(self, tool: str, host_path: str, target: str,
                             retries_left: int) -> None:
        """Parse the scratch output file a completed hydra/ncrack run
        wrote and feed it into Results Display's Credentials Found view.
        Same empty-vs-not-yet-written ambiguity as _ingest_nmap_xml, same
        retry-on-timer approach — also the same behavior if the tool
        genuinely found zero credentials (retries exhaust, nothing shown),
        which is indistinguishable from "not written yet" without deeper
        inspection and is an accepted tradeoff already made for the nmap
        path."""
        parser = parse_hydra_output if tool == "hydra" else parse_ncrack_output
        creds = parser(host_path)
        if creds:
            stamp = datetime.now().strftime("%H:%M:%S")
            self.main_area.results_tab.add_credential_results(tool, target, creds, stamp)
            try:
                os.remove(host_path)
            except OSError:
                pass
            return
        if retries_left > 0:
            QTimer.singleShot(
                self._XML_READ_RETRY_MS,
                lambda: self._ingest_credentials(tool, host_path, target, retries_left - 1),
            )

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
            self.top_bar.target_input.setText(target)
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
        reply = QMessageBox.question(
            self, "Quit",
            "Close TheRecon? This will stop all running terminals"
            + (" and shut down WSL." if os.name == "nt" else "."),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            event.ignore()
            return

        stop = getattr(self.main_area.wizard_tab, "stop_all", None)
        if callable(stop):
            stop()
        for term in (self.main_area.raw_output_tab.terminal, self.main_area.llm_tab):
            stop = getattr(term, "stop", None)
            if callable(stop):
                stop()

        if os.name == "nt":
            import subprocess
            try:
                # --shutdown tears down the whole WSL2 VM (not tied to a
                # distro name), so this works regardless of which distro
                # the user has installed/set as default.
                subprocess.run(
                    ["wsl.exe", "--shutdown"],
                    timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

        super().closeEvent(event)
