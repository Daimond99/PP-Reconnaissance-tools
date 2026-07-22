"""
Tool Selection tab — Windows-native tool menu.

Nmap (via Wizard Console), Ncat, and Evil-WinRM are enabled for real
execution on Windows. Masscan / Hydra / Ncrack stay disabled until a
Windows-native path exists.

Both Ncat and Evil-WinRM wizards share the exact same safety pipeline as
every other execution path in the app:
    validate input -> ConfirmationGate.request() -> preview box -> exact
    "yes" -> QProcess execution (streamed) -> audit log.

Evil-WinRM's password is entered through a dedicated QLineEdit(Password) —
never the console text area — and is masked with asterisks in both the
Command Preview and the audit log. Only the in-memory argv passed to
QProcess ever contains the real password.
"""

from __future__ import annotations

import os
from enum import Enum, auto
from typing import List, Optional

from PySide6.QtCore import Qt, QProcess, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
)

from src.config import (
    TERMINAL_FONT_FAMILY, TERMINAL_FONT_SIZE, CONSOLE_BG, CONSOLE_TEXT,
    AUTHORIZED_SCOPE, TOOL_ENABLEMENT, TOOL_NOT_SUPPORTED_MESSAGE,
    NCRACK_STABILITY_WARNING, NCRACK_PROTOCOLS,
)
from src.core.confirmation_gate import ConfirmationGate
from src.core.wizard_safety import (
    validate_target, validate_port_range, validate_username, validate_password,
    validate_file_path, quote_arg,
)


class ToolState(Enum):
    MENU = auto()
    NCAT_MODE = auto()
    NCAT_TARGET = auto()
    NCAT_PORT = auto()
    NCAT_CONFIRM = auto()
    NCAT_RUNNING = auto()
    EWR_TARGET = auto()
    EWR_USERNAME = auto()
    EWR_CONFIRM = auto()
    EWR_RUNNING = auto()
    NCRACK_WARNING = auto()
    NCRACK_TARGET = auto()
    NCRACK_PROTOCOL = auto()
    NCRACK_USERLIST = auto()
    NCRACK_PASSLIST = auto()
    NCRACK_CONFIRM = auto()
    NCRACK_RUNNING = auto()


class ToolSelectionTab(QWidget):
    """Tab สำหรับ Tool Selection — Ncat / Evil-WinRM (Windows native)."""

    commandEntered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.state = ToolState.MENU

        # Ncat working state
        self._ncat_mode: Optional[str] = None       # "connect" | "listen"
        self._ncat_target: str = ""
        self._ncat_port: str = ""

        # Evil-WinRM working state
        self._ewr_target: str = ""
        self._ewr_username: str = ""

        # Ncrack working state
        self._ncrack_target: str = ""
        self._ncrack_protocol: str = ""
        self._ncrack_userlist: str = ""
        self._ncrack_passlist: str = ""

        self.gate: Optional[ConfirmationGate] = None
        self._proc: Optional[QProcess] = None

        self._build_ui()
        self._show_menu()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = QFont(TERMINAL_FONT_FAMILY, TERMINAL_FONT_SIZE)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(False)
        self.output_area.setAcceptRichText(False)
        self.output_area.setFont(font)
        self.output_area.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; border-radius: 4px; padding: 20px 24px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13.5px;
        """)
        layout.addWidget(self.output_area, 1)
        self.console = self.output_area

        self._original_key_handler = self.output_area.keyPressEvent
        self.output_area.keyPressEvent = self._on_key_press
        self._input_enabled = True
        self._input_start_pos = 0

        # Masked password entry bar — hidden unless collecting Evil-WinRM's
        # password. Real QLineEdit(Password), never the console text area.
        self.pass_bar = QWidget()
        self.pass_bar.setStyleSheet(f"background-color: {CONSOLE_BG};")
        pass_bar_layout = QHBoxLayout(self.pass_bar)
        pass_bar_layout.setContentsMargins(24, 10, 24, 14)
        pass_bar_layout.setSpacing(10)

        self.pass_label = QLabel("Password>")
        self.pass_label.setStyleSheet(f"color: {CONSOLE_TEXT}; font-family: 'Consolas', monospace;")
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("พิมพ์ password แล้วกด Enter (จะไม่แสดงตัวอักษร)")
        self.pass_submit = QPushButton("Submit")

        pass_bar_layout.addWidget(self.pass_label)
        pass_bar_layout.addWidget(self.pass_input, 1)
        pass_bar_layout.addWidget(self.pass_submit)
        self.pass_bar.hide()
        layout.addWidget(self.pass_bar)

        self.pass_input.returnPressed.connect(self._submit_password)
        self.pass_submit.clicked.connect(self._submit_password)

    def _on_key_press(self, event: QKeyEvent):
        # Ctrl+C always works, even mid-execution, to cancel a running
        # Ncat listen session or an active Evil-WinRM connection.
        if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            self._cancel_running_process()
            return

        if not self._input_enabled:
            return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.output_area.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            line = cursor.selectedText()
            cmd = line.split(">")[-1].strip() if ">" in line else line.strip()
            if cmd:
                self._on_input(cmd)
            return
        if event.key() in (Qt.Key_Backspace, Qt.Key_Left):
            cursor = self.output_area.textCursor()
            line_text = cursor.block().text()
            col = cursor.positionInBlock()
            if ">" in line_text:
                prompt_pos = line_text.find(">") + 1
                if col <= prompt_pos:
                    return
        self._original_key_handler(event)

    # ------------------------------------------------------------------
    # Console helpers
    # ------------------------------------------------------------------

    def _append(self, text: str):
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    def _clear(self):
        self.output_area.clear()

    def write_output(self, text: str):
        self._append(text)

    # ------------------------------------------------------------------
    # Input dispatch
    # ------------------------------------------------------------------

    def _on_input(self, text: str):
        if self.state == ToolState.MENU:
            self._handle_menu(text)
        elif self.state == ToolState.NCAT_MODE:
            self._handle_ncat_mode(text)
        elif self.state == ToolState.NCAT_TARGET:
            self._handle_ncat_target(text)
        elif self.state == ToolState.NCAT_PORT:
            self._handle_ncat_port(text)
        elif self.state == ToolState.NCAT_CONFIRM:
            self._handle_ncat_confirm(text)
        elif self.state == ToolState.EWR_TARGET:
            self._handle_ewr_target(text)
        elif self.state == ToolState.EWR_USERNAME:
            self._handle_ewr_username(text)
        elif self.state == ToolState.EWR_CONFIRM:
            self._handle_ewr_confirm(text)
        elif self.state == ToolState.NCRACK_WARNING:
            self._handle_ncrack_warning(text)
        elif self.state == ToolState.NCRACK_TARGET:
            self._handle_ncrack_target(text)
        elif self.state == ToolState.NCRACK_PROTOCOL:
            self._handle_ncrack_protocol(text)
        elif self.state == ToolState.NCRACK_USERLIST:
            self._handle_ncrack_userlist(text)
        elif self.state == ToolState.NCRACK_PASSLIST:
            self._handle_ncrack_passlist(text)
        elif self.state == ToolState.NCRACK_CONFIRM:
            self._handle_ncrack_confirm(text)
        else:
            self._append("\n[!] กำลังประมวลผลอยู่ กรุณารอสักครู่ (Ctrl+C เพื่อยกเลิก)\n")

    # ------------------------------------------------------------------
    # Tool Selection menu
    # ------------------------------------------------------------------

    def _status_badge(self, tool: str) -> str:
        return "✓ enabled " if TOOL_ENABLEMENT.get(tool, False) else "x disabled"

    def _show_menu(self):
        self.state = ToolState.MENU
        self._clear()
        self._append(
            "TOOL SELECTION MENU\n"
            + "=" * 50 + "\n\n"
            f" 1. Nmap        [{self._status_badge('nmap')}] — ใช้งานผ่านแท็บ 'Wizard Console'\n"
            f" 2. Ncat        [{self._status_badge('ncat')}]\n"
            f" 3. Evil-WinRM  [{self._status_badge('evil-winrm')}]\n"
            f" 4. Masscan     [{self._status_badge('masscan')}]\n"
            f" 5. Hydra       [{self._status_badge('hydra')}]\n"
            f" 6. Ncrack      [{self._status_badge('ncrack')}]\n\n"
            "Select option (1-6) : \n"
            "Select>"
        )

    def _handle_menu(self, text: str):
        choice = text.strip()
        tool_map = {
            "1": "nmap", "2": "ncat", "3": "evil-winrm",
            "4": "masscan", "5": "hydra", "6": "ncrack",
        }
        tool = tool_map.get(choice)
        if not tool:
            self._append(f"\n[!] เลือกไม่ถูกต้อง: {choice}\n\nSelect option (1-6): ")
            return

        if not TOOL_ENABLEMENT.get(tool, False):
            self._append(f"\n{TOOL_NOT_SUPPORTED_MESSAGE}\n\nSelect>")
            return

        if tool == "nmap":
            self._append("\n[i] Nmap ใช้งานผ่านแท็บ 'Wizard Console' หรือ 'LLM Mode' ครับ\n\nSelect>")
            return
        if tool == "ncat":
            self._show_ncat_mode_select()
            return
        if tool == "evil-winrm":
            self._show_ewr_target()
            return
        if tool == "ncrack":
            self._show_ncrack_warning()
            return

    # ------------------------------------------------------------------
    # Ncat wizard — connect mode / listen mode
    # ------------------------------------------------------------------

    def _show_ncat_mode_select(self):
        self.state = ToolState.NCAT_MODE
        self._clear()
        self._append(
            "NCAT — เลือกโหมดการทำงาน\n"
            + "=" * 40 + "\n\n"
            " 1. Connect mode  (ncat <target> <port>)\n"
            " 2. Listen mode   (ncat -lvnp <port>) — เปิด port รอรับการเชื่อมต่อ\n"
            " 3. กลับเมนูหลัก\n\n"
            "Select>"
        )

    def _handle_ncat_mode(self, text: str):
        choice = text.strip()
        if choice == "1":
            self._ncat_mode = "connect"
            self.state = ToolState.NCAT_TARGET
            self._append("\nระบุ target (IP/hostname):\nTarget>")
        elif choice == "2":
            self._ncat_mode = "listen"
            self.state = ToolState.NCAT_PORT
            self._append("\nระบุ port ที่ต้องการเปิดรอรับการเชื่อมต่อ:\nPort>")
        elif choice == "3":
            self._show_menu()
        else:
            self._append(f"\n[!] เลือกไม่ถูกต้อง: {choice}\nSelect>")

    def _handle_ncat_target(self, text: str):
        ok, result = validate_target(text)
        if not ok:
            self._append(f"\n[!] {result}\nTarget>")
            return
        self._ncat_target = result
        self.state = ToolState.NCAT_PORT
        self._append("\nระบุ port:\nPort>")

    def _handle_ncat_port(self, text: str):
        ok, result = validate_port_range(text)
        if not ok:
            self._append(f"\n[!] {result}\nPort>")
            return
        # Ncat connects/listens on a single port — take the first token if a
        # range/list was entered.
        port = result.replace(",", "-").split("-")[0]
        self._ncat_port = port
        self._prepare_ncat_preview()

    def _prepare_ncat_preview(self):
        if self._ncat_mode == "connect":
            argv = ["ncat", self._ncat_target, self._ncat_port]
            command = " ".join(argv)
            extra_impact = (
                f"จะเชื่อมต่อขาออก (outbound) ไปยัง {self._ncat_target}:{self._ncat_port} โดยตรง"
            )
            self.gate = ConfirmationGate(channel="ncat")
            result = self.gate.request(command, self._ncat_target, extra_impact=extra_impact)
        else:
            argv = ["ncat", "-lvnp", self._ncat_port]
            command = " ".join(argv)
            extra_impact = (
                "[!] Listen mode จะเปิด port รอรับการเชื่อมต่อจากภายนอกเข้ามาที่เครื่องนี้ "
                "— ตรวจสอบ firewall และสิทธิ์การใช้งานก่อนยืนยัน"
            )
            # No remote target to scope-check — this binds locally.
            self.gate = ConfirmationGate(channel="ncat")
            result = self.gate.request(
                command, f"local:{self._ncat_port} (listen)",
                extra_impact=extra_impact, skip_scope=True,
            )

        if not result.ok:
            self._append(f"\n{result.message}\n\nSelect>")
            self.state = ToolState.MENU
            return

        self._append(f"\n{result.preview_box}\n")
        self.state = ToolState.NCAT_CONFIRM

    def _handle_ncat_confirm(self, text: str):
        reply = text.strip()
        if self.gate.confirm(reply):
            self._append("\n[✓] ยืนยันแล้ว กำลังรันคำสั่ง (Ctrl+C เพื่อยกเลิก)...\n\n")
            self._run_process(self.gate.argv, ToolState.NCAT_RUNNING)
        else:
            self.gate.cancel(reply)
            self._append("\n[x] ยกเลิกคำสั่งแล้ว\n\n")
            self._show_menu()

    # ------------------------------------------------------------------
    # Evil-WinRM wizard
    # ------------------------------------------------------------------

    def _show_ewr_target(self):
        self.state = ToolState.EWR_TARGET
        self._clear()
        self._append(
            "EVIL-WINRM — เข้าถึงระบบเป้าหมายผ่าน WinRM\n"
            + "=" * 45 + "\n\n"
            f"(scope ที่อนุญาต: {AUTHORIZED_SCOPE})\n\n"
            "ระบุ target (IP/hostname):\nTarget>"
        )

    def _handle_ewr_target(self, text: str):
        ok, result = validate_target(text)
        if not ok:
            self._append(f"\n[!] {result}\nTarget>")
            return
        self._ewr_target = result
        self.state = ToolState.EWR_USERNAME
        self._append("\nระบุ username:\nUsername>")

    def _handle_ewr_username(self, text: str):
        ok, result = validate_username(text)
        if not ok:
            self._append(f"\n[!] {result}\nUsername>")
            return
        self._ewr_username = result
        self._append(
            "\nระบุ password (จะไม่แสดงตัวอักษรขณะพิมพ์เพื่อความปลอดภัย — "
            "กรอกในช่องด้านล่างแล้วกด Enter)\n"
        )
        self._input_enabled = False
        self.output_area.setReadOnly(True)
        self.pass_bar.show()
        self.pass_input.setFocus()

    def _submit_password(self):
        if self.state != ToolState.EWR_USERNAME:
            return
        password = self.pass_input.text()
        self.pass_input.clear()
        if not password:
            return

        ok, result = validate_password(password)
        self.pass_bar.hide()
        self.output_area.setReadOnly(False)
        self._input_enabled = True

        if not ok:
            self._append(f"\n[!] {result}\n")
            self.pass_bar.show()
            self.output_area.setReadOnly(True)
            self.pass_input.setFocus()
            return

        masked = "*" * max(len(password), 8)
        display_command = f"evil-winrm -i {self._ewr_target} -u {self._ewr_username} -p {masked}"
        real_argv = ["evil-winrm", "-i", self._ewr_target, "-u", self._ewr_username, "-p", password]
        extra_impact = (
            "[!!!] คำเตือนระดับสูงสุด: การเชื่อมต่อนี้จะเข้าถึงระบบเป้าหมายโดยตรง "
            "และได้ shell access จริงหากยืนยันสำเร็จ — ตรวจสอบสิทธิ์การใช้งานให้แน่ใจก่อน"
        )

        self.gate = ConfirmationGate(channel="evil-winrm")
        result = self.gate.request(
            display_command, self._ewr_target,
            extra_impact=extra_impact, argv_override=real_argv,
        )
        if not result.ok:
            self._append(f"\n{result.message}\n\nSelect>")
            self._show_menu()
            return

        self._append(f"\n{result.preview_box}\n")
        self.state = ToolState.EWR_CONFIRM

    def _handle_ewr_confirm(self, text: str):
        reply = text.strip()
        if self.gate.confirm(reply):
            self._append("\n[✓] ยืนยันแล้ว กำลังเชื่อมต่อ (Ctrl+C เพื่อตัด session)...\n\n")
            self._run_process(self.gate.argv, ToolState.EWR_RUNNING)
        else:
            self.gate.cancel(reply)
            self._append("\n[x] ยกเลิกคำสั่งแล้ว\n\n")
            self._show_menu()

    # ------------------------------------------------------------------
    # Ncrack wizard — mandatory Windows-stability warning, then
    # target -> protocol (pick-list) -> userlist -> passlist -> confirm
    # ------------------------------------------------------------------

    def _show_ncrack_warning(self):
        self.state = ToolState.NCRACK_WARNING
        self._clear()
        self._append(f"{NCRACK_STABILITY_WARNING}\nSelect>")

    def _handle_ncrack_warning(self, text: str):
        answer = text.strip().lower()
        if answer in ("yes", "y"):
            self._show_ncrack_target()
        elif answer in ("no", "n"):
            self._append("\n[x] ยกเลิก — กลับไปที่เมนู Tool Selection\n\n")
            self._show_menu()
        else:
            self._append("\n[!] กรุณาตอบ yes หรือ no\nSelect>")

    def _show_ncrack_target(self):
        self.state = ToolState.NCRACK_TARGET
        self._clear()
        self._append(
            "NCRACK — Credential Brute-force Testing\n"
            + "=" * 45 + "\n\n"
            f"(scope ที่อนุญาต: {AUTHORIZED_SCOPE})\n\n"
            "ระบุ target (IP/hostname):\nTarget>"
        )

    def _handle_ncrack_target(self, text: str):
        ok, result = validate_target(text)
        if not ok:
            self._append(f"\n[!] {result}\nTarget>")
            return
        self._ncrack_target = result
        self._show_ncrack_protocol()

    def _show_ncrack_protocol(self):
        self.state = ToolState.NCRACK_PROTOCOL
        lines = "\n".join(f" {i}. {proto}" for i, proto in enumerate(NCRACK_PROTOCOLS, start=1))
        prompt = (
            f"\nเลือก service/protocol ที่จะทดสอบ:\n{lines}\n\n"
            f"Select option (1-{len(NCRACK_PROTOCOLS)}) : \nSelect>"
        )
        self._append(prompt)

    def _handle_ncrack_protocol(self, text: str):
        choice = text.strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(NCRACK_PROTOCOLS)):
            self._append(f"\n[!] เลือกไม่ถูกต้อง: {choice}\nSelect>")
            return
        self._ncrack_protocol = NCRACK_PROTOCOLS[int(choice) - 1]
        self.state = ToolState.NCRACK_USERLIST
        self._append("\nระบุ path ของ userlist:\nUserlist>")

    def _validate_existing_file(self, raw_path: str):
        ok, result = validate_file_path(raw_path)
        if not ok:
            return False, result
        if not os.path.isfile(result):
            return False, f"ไม่พบไฟล์: {result}"
        return True, result

    def _handle_ncrack_userlist(self, text: str):
        ok, result = self._validate_existing_file(text)
        if not ok:
            self._append(f"\n[!] {result}\nUserlist>")
            return
        self._ncrack_userlist = result
        self.state = ToolState.NCRACK_PASSLIST
        self._append("\nระบุ path ของ passlist:\nPasslist>")

    def _handle_ncrack_passlist(self, text: str):
        ok, result = self._validate_existing_file(text)
        if not ok:
            self._append(f"\n[!] {result}\nPasslist>")
            return
        self._ncrack_passlist = result
        self._prepare_ncrack_preview()

    def _prepare_ncrack_preview(self):
        argv = [
            "ncrack", "-U", self._ncrack_userlist, "-P", self._ncrack_passlist,
            f"{self._ncrack_protocol}://{self._ncrack_target}",
        ]
        command = " ".join(quote_arg(tok) for tok in argv)
        extra_impact = (
            f"ทดสอบ credential แบบ brute-force ผ่าน {self._ncrack_protocol} "
            "อาจใช้เวลานานและมีความเสี่ยง lock account เป้าหมายถ้ามีระบบ lockout policy — "
            "บน Windows อาจพบปัญหาด้าน stability มากกว่าปกติ"
        )
        self.gate = ConfirmationGate(channel="ncrack")
        result = self.gate.request(command, self._ncrack_target, extra_impact=extra_impact)
        if not result.ok:
            self._append(f"\n{result.message}\n\nSelect>")
            self.state = ToolState.MENU
            return

        self._append(f"\n{result.preview_box}\n")
        self.state = ToolState.NCRACK_CONFIRM

    def _handle_ncrack_confirm(self, text: str):
        reply = text.strip()
        if self.gate.confirm(reply):
            self._append("\n[✓] ยืนยันแล้ว กำลังรันคำสั่ง (Ctrl+C เพื่อยกเลิก)...\n\n")
            # Note: raw ncrack stdout (which may contain recovered
            # credentials) is only streamed to this console — never written
            # to the audit log. The audit log only ever records
            # command/target/protocol/confirm-cancel, never plaintext
            # credentials.
            self._run_process(self.gate.argv, ToolState.NCRACK_RUNNING)
        else:
            self.gate.cancel(reply)
            self._append("\n[x] ยกเลิกคำสั่งแล้ว\n\n")
            self._show_menu()

    # ------------------------------------------------------------------
    # Shared QProcess execution (streamed, non-blocking, Ctrl+C cancellable)
    # ------------------------------------------------------------------

    def _run_process(self, argv: List[str], running_state: ToolState):
        self.state = running_state
        self._input_enabled = False
        self.output_area.setReadOnly(True)

        proc = QProcess(self)
        self._proc = proc
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_proc_output)
        proc.finished.connect(self._on_proc_finished)
        proc.errorOccurred.connect(self._on_proc_error)
        proc.start(argv[0], argv[1:])
        self.commandEntered.emit(" ".join(argv))

    def _on_proc_output(self):
        if not self._proc:
            return
        chunk = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        self._append(chunk)

    def _on_proc_error(self, error):
        self._append(f"\n[!] เกิดข้อผิดพลาดขณะรันคำสั่ง: {error}\n\n")
        self._proc = None
        self._input_enabled = True
        self.output_area.setReadOnly(False)
        self._show_menu()

    def _on_proc_finished(self, exit_code, exit_status):
        if self.gate:
            self.gate.mark_executed_result(exit_code)
        self._proc = None
        self._append(f"\n\n[เสร็จสิ้น, exit code {exit_code}]\n\n")
        self._input_enabled = True
        self.output_area.setReadOnly(False)
        self._show_menu()

    def _cancel_running_process(self):
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
            if self.gate:
                self.gate.cancel("ctrl_c_cancelled")
            self._append("\n\n[x] ยกเลิกด้วย Ctrl+C\n\n")
            self._proc = None
            self._input_enabled = True
            self.output_area.setReadOnly(False)
            self._show_menu()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
        super().closeEvent(event)
