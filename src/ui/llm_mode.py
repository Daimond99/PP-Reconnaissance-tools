"""
LLM Mode tab — natural-language-to-nmap console with two sub-modes:

  Plain LLM-Nmap : local-only translation via `llm` CLI + llm-tools-nmap,
                   talking to a local model (e.g. Ollama). No external API,
                   no API key.
  AI Mode        : same `llm` CLI + llm-tools-nmap plugin, but pointed at an
                   external provider (OpenAI / Anthropic) for smarter
                   translation and a natural-language result summary.

Both modes share the exact same safety pipeline as the rest of the app:
  translate (LLM) -> ConfirmationGate.request() -> preview box -> exact
  "yes" -> QProcess execution -> audit log.

No command coming from an LLM is ever executed without that explicit human
"yes". API keys are never written to disk except via the OS keyring
(through APIKeyManager), never logged, and the masked entry field is a real
QLineEdit(Password) — not the console text area — so a key can never end up
in the console's scrollback.
"""

from __future__ import annotations

import html as html_lib
import re
from enum import Enum, auto
from typing import List, Optional

from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
)

from src.config import (
    TERMINAL_FONT_FAMILY, TERMINAL_FONT_SIZE,
    CONSOLE_BG, CONSOLE_TEXT, AUTHORIZED_SCOPE, AI_MODE_PROVIDERS, SYSTEM_PROMPT,
    LLM_TOOLS_NMAP_PATH,
    PURPLE, BLUE,
    ACCENT_GREEN, ACCENT_RED, ACCENT_CYAN,
)
from src.core.api_key_manager import get_api_key_manager
from src.core.confirmation_gate import ConfirmationGate
from src.core.wizard_safety import is_recon_related, validate_ai_response


_TARGET_RE = re.compile(r"((?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?)")


class LLMState(Enum):
    MODE_SELECT = auto()
    AI_PROVIDER_SELECT = auto()
    AI_KEY_ENTRY = auto()
    AI_KEY_SAVE_PROMPT = auto()
    AI_OFFTOPIC_CONFIRM = auto()
    READY = auto()
    CONFIRM = auto()
    RUNNING = auto()


class LLMModeTab(QWidget):
    """Tab สำหรับ LLM Mode — Plain LLM-Nmap / AI Mode."""

    commandEntered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.key_manager = get_api_key_manager()

        self.state = LLMState.MODE_SELECT
        self.mode: Optional[str] = None       # "plain" | "ai"
        self.provider: Optional[str] = None   # "openai" | "anthropic"
        self.gate: Optional[ConfirmationGate] = None

        self._provider_menu_order: List[str] = list(AI_MODE_PROVIDERS)
        self._pending_provider_choice: Optional[str] = None
        self._pending_valid_key: Optional[str] = None
        self._pending_target: str = AUTHORIZED_SCOPE
        self._pending_user_text: str = ""
        self._pending_offtopic_text: str = ""

        self._translate_proc: Optional[QProcess] = None
        self._exec_proc: Optional[QProcess] = None
        self._summary_proc: Optional[QProcess] = None
        self._exec_output_buf: List[str] = []

        self._history: List[str] = []
        self._history_index = -1

        self._build_ui()
        self._show_mode_select()

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
        self.output_area.keyPressEvent = self._make_key_handler(self.output_area.keyPressEvent)

        # Masked API-key entry bar — hidden unless we're collecting a key.
        # A real QLineEdit(Password) so the key never touches the console's
        # plain-text scrollback/history.
        self.key_bar = QWidget()
        self.key_bar.setStyleSheet(f"background-color: {CONSOLE_BG};")
        key_bar_layout = QHBoxLayout(self.key_bar)
        key_bar_layout.setContentsMargins(24, 10, 24, 14)
        key_bar_layout.setSpacing(10)

        self.key_label = QLabel("API Key>")
        self.key_label.setStyleSheet(f"color: {CONSOLE_TEXT}; font-family: 'Consolas', monospace;")
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("วาง API key แล้วกด Enter (จะไม่แสดงตัวอักษร)")
        self.key_submit = QPushButton("Submit")

        key_bar_layout.addWidget(self.key_label)
        key_bar_layout.addWidget(self.key_input, 1)
        key_bar_layout.addWidget(self.key_submit)
        self.key_bar.hide()
        layout.addWidget(self.key_bar)

        self.key_input.returnPressed.connect(self._submit_key_input)
        self.key_submit.clicked.connect(self._submit_key_input)

    def _make_key_handler(self, original_handler):
        def handler(event):
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
            original_handler(event)
        return handler

    # ------------------------------------------------------------------
    # Console helpers
    # ------------------------------------------------------------------

    def _append(self, text: str):
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(self._colorize(text))
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    _NUM_OPTION_RE = re.compile(r"^(\s*)(\d+\.)(\s.*)$")

    def _colorize_line(self, line: str) -> str:
        """Detect a message-type marker in a raw (unescaped) line and wrap
        it in a colored span, escaping the text content along the way."""
        stripped = line.strip()
        esc = html_lib.escape(line)

        if stripped.startswith("[!]"):
            return f'<span style="color:{ACCENT_RED};font-weight:600">{esc}</span>'
        if stripped.startswith("[✓]"):
            return f'<span style="color:{ACCENT_GREEN};font-weight:600">{esc}</span>'
        if stripped.startswith("[…]") or stripped.startswith("[...]"):
            return f'<span style="color:{ACCENT_CYAN}">{esc}</span>'
        if stripped.startswith("[x]"):
            return f'<span style="color:{ACCENT_RED}">{esc}</span>'
        if stripped.startswith("[i]"):
            return f'<span style="color:{BLUE}">{esc}</span>'
        if stripped.startswith(("[AI Summary]", "[Summary]", "[llm output]")):
            return f'<span style="color:{ACCENT_CYAN};font-weight:700">{esc}</span>'
        if stripped and set(stripped) == {"="}:
            return f'<span style="color:{PURPLE}">{esc}</span>'
        if stripped.startswith("LLM MODE"):
            return f'<span style="color:{PURPLE};font-weight:700">{esc}</span>'
        if stripped in (">", "Select>") or stripped.endswith("Select>"):
            prefix = line[: line.rfind(">")]
            return f'{html_lib.escape(prefix)}<span style="color:{PURPLE};font-weight:700">&gt;</span>'
        m = self._NUM_OPTION_RE.match(line)
        if m:
            return (
                f'{html_lib.escape(m.group(1))}'
                f'<span style="color:{BLUE};font-weight:700">{html_lib.escape(m.group(2))}</span>'
                f'{html_lib.escape(m.group(3))}'
            )
        return esc

    def _colorize(self, text: str) -> str:
        lines = text.split("\n")
        return "<br>".join(self._colorize_line(line) for line in lines)

    def _clear(self):
        self.output_area.clear()

    def write_output(self, text: str):
        self._append(text)

    # ------------------------------------------------------------------
    # Input dispatch
    # ------------------------------------------------------------------

    def _on_input(self, text: str):
        self._history.append(text)
        self._history_index = len(self._history)

        if self.state == LLMState.MODE_SELECT:
            self._handle_mode_select(text)
        elif self.state == LLMState.AI_PROVIDER_SELECT:
            self._handle_provider_select(text)
        elif self.state == LLMState.AI_KEY_SAVE_PROMPT:
            self._handle_save_prompt(text)
        elif self.state == LLMState.AI_OFFTOPIC_CONFIRM:
            self._handle_offtopic_confirm(text)
        elif self.state == LLMState.CONFIRM:
            self._handle_confirmation(text)
        elif self.state == LLMState.READY:
            self._handle_ready_input(text)
        else:
            self._append("\n[!] กำลังประมวลผลอยู่ กรุณารอสักครู่...\n")

    # ------------------------------------------------------------------
    # Mode selection
    # ------------------------------------------------------------------

    def _show_mode_select(self):
        self.state = LLMState.MODE_SELECT
        self._clear()
        self._append(
            "LLM MODE — เลือกโหมดการทำงาน\n"
            + "=" * 50 + "\n\n"
            " 1. Plain LLM-Nmap  — local เท่านั้น ไม่ต้องใช้ API key (Ollama)\n"
            " 2. AI Mode         — เชื่อมต่อ OpenAI/Anthropic/Gemini API เพื่อคำตอบที่ฉลาดกว่า\n\n"
            "Select option (1-2) : \n"
            "Select>"
        )

    def _handle_mode_select(self, text: str):
        choice = text.strip()
        if choice == "1":
            self.mode = "plain"
            self.provider = None
            self._enter_ready("Plain LLM-Nmap Mode พร้อมใช้งาน (local only, ไม่มีการเรียก API ภายนอก)")
        elif choice == "2":
            self.mode = "ai"
            self._enter_ai_mode()
        else:
            self._append(f"\n[!] เลือกไม่ถูกต้อง: {choice}\n\nSelect option (1-2): ")

    # ------------------------------------------------------------------
    # AI Mode — API key management (Claude-Code-style)
    # ------------------------------------------------------------------

    def _enter_ai_mode(self):
        for provider in AI_MODE_PROVIDERS:
            if self.key_manager.has_key(provider):
                self.provider = provider
                label = AI_MODE_PROVIDERS[provider]["label"]
                self._enter_ready(
                    f"AI Mode พร้อมใช้งาน — ใช้ {label} (พบ API key ที่บันทึกไว้)\n"
                    "พิมพ์ 'reset-key' เพื่อเปลี่ยน/ลบ API key"
                )
                return
        self._show_provider_select()

    def _show_provider_select(self):
        self.state = LLMState.AI_PROVIDER_SELECT
        self._clear()
        provider_ids = list(AI_MODE_PROVIDERS)
        self._provider_menu_order = provider_ids
        lines = ["[AI Mode] ยังไม่พบ API key กรุณาเลือกผู้ให้บริการ:"]
        for idx, provider in enumerate(provider_ids, start=1):
            lines.append(f" {idx}. {AI_MODE_PROVIDERS[provider]['label']}")
        cancel_idx = len(provider_ids) + 1
        lines.append(f" {cancel_idx}. ยกเลิกและกลับไปใช้ Plain LLM-Nmap แทน")
        lines.append("Select> ")
        self._append("\n".join(lines))

    def _handle_provider_select(self, text: str):
        choice = text.strip()
        provider_ids = getattr(self, "_provider_menu_order", list(AI_MODE_PROVIDERS))
        cancel_idx = len(provider_ids) + 1

        if choice.isdigit() and 1 <= int(choice) <= len(provider_ids):
            self._pending_provider_choice = provider_ids[int(choice) - 1]
        elif choice == str(cancel_idx):
            self.mode = "plain"
            self.provider = None
            self._enter_ready("กลับไปใช้ Plain LLM-Nmap Mode")
            return
        else:
            self._append(f"\n[!] เลือกไม่ถูกต้อง: {choice}\nSelect> ")
            return

        self.state = LLMState.AI_KEY_ENTRY
        label = AI_MODE_PROVIDERS[self._pending_provider_choice]["label"]
        self._append(
            f"\nระบุ API key ของคุณสำหรับ {label}\n"
            "(จะไม่แสดงตัวอักษรขณะพิมพ์เพื่อความปลอดภัย — กรอกในช่องด้านล่างแล้วกด Enter)\n"
        )
        self.output_area.setReadOnly(True)
        self.key_bar.show()
        self.key_input.setFocus()

    def _submit_key_input(self):
        if self.state != LLMState.AI_KEY_ENTRY:
            return
        key = self.key_input.text()
        self.key_input.clear()
        if not key.strip():
            return

        self.key_bar.hide()
        self.output_area.setReadOnly(False)
        self._append("Validating API key...\n")

        result = self.key_manager.validate_key(self._pending_provider_choice, key)
        if not result.ok:
            self._append(f"[!] {result.message}\nลองใหม่อีกครั้ง\n")
            self.key_bar.show()
            self.output_area.setReadOnly(True)
            self.key_input.setFocus()
            return

        self._pending_valid_key = key
        self.provider = self._pending_provider_choice
        self.key_manager.set_session_key(self.provider, key)  # usable immediately this session
        self.state = LLMState.AI_KEY_SAVE_PROMPT
        self._append(
            f"[✓] {result.message}\n\n"
            "ต้องการบันทึก API key นี้ไว้ใช้ครั้งถัดไปหรือไม่? (yes/no)\n"
            "หากเลือก no จะต้องกรอกใหม่ทุกครั้งที่เปิดโปรแกรม\n"
            "Select> "
        )

    def _handle_save_prompt(self, text: str):
        answer = text.strip().lower()
        if answer in ("yes", "y"):
            ok, msg = self.key_manager.save_key(self.provider, self._pending_valid_key)
            self._append(f"\n{'[✓]' if ok else '[!]'} {msg}\n")
        elif answer in ("no", "n"):
            self._append("\n[i] API key จะถูกเก็บไว้ใน session นี้เท่านั้น (ลบเมื่อปิดโปรแกรม)\n")
        else:
            self._append("\n[!] กรุณาตอบ yes หรือ no\nSelect> ")
            return

        self._pending_valid_key = None
        label = AI_MODE_PROVIDERS[self.provider]["label"]
        self._enter_ready(f"AI Mode พร้อมใช้งาน — {label}\nพิมพ์ 'reset-key' เพื่อเปลี่ยน/ลบ API key")

    def _handle_reset_key(self):
        if self.mode != "ai" or not self.provider:
            self._append("\n[i] Plain Mode ไม่ได้ใช้ API key\n\n>")
            return
        self.key_manager.delete_key(self.provider)
        self._append(f"\n[✓] ลบ API key ของ {AI_MODE_PROVIDERS[self.provider]['label']} แล้ว\n")
        self._show_provider_select()

    # ------------------------------------------------------------------
    # READY — accept natural-language queries
    # ------------------------------------------------------------------

    def _enter_ready(self, banner: str):
        self.state = LLMState.READY
        self._clear()
        self._append(
            f"{banner}\n"
            f"(scope ที่อนุญาต: {AUTHORIZED_SCOPE})\n\n"
            'พิมพ์คำสั่งภาษาคน เช่น "หา web server ที่เปิดอยู่ใน 192.168.1.0/24"\n'
            "(พิมพ์ 'reset-key' เพื่อจัดการ API key, 'mode' เพื่อสลับโหมด)\n\n>"
        )

    def _handle_ready_input(self, text: str):
        cmd = text.strip()
        low = cmd.lower()
        if low == "reset-key":
            self._handle_reset_key()
            return
        if low == "mode":
            self._show_mode_select()
            return
        if not cmd:
            self._append("\n>")
            return

        # Client-side pre-filter — AI Mode only, to avoid spending API
        # credit on obviously off-topic requests. Plain Mode is local/free
        # so it always goes straight through to translation.
        if self.mode == "ai" and not is_recon_related(cmd):
            self._pending_offtopic_text = cmd
            self.state = LLMState.AI_OFFTOPIC_CONFIRM
            self._append(
                "\n[!] คำขอนี้ดูไม่เกี่ยวข้องกับ network recon "
                "ต้องการส่งไปให้ AI ตอบต่อหรือไม่? (yes/no)\n"
                "Select> "
            )
            return

        self._translate_and_preview(cmd)

    def _handle_offtopic_confirm(self, text: str):
        answer = text.strip().lower()
        if answer in ("yes", "y"):
            pending = self._pending_offtopic_text
            self._pending_offtopic_text = ""
            self._translate_and_preview(pending)
        elif answer in ("no", "n"):
            self._pending_offtopic_text = ""
            self._append("\n[x] ยกเลิกคำขอ\n\n>")
            self.state = LLMState.READY
        else:
            self._append("\n[!] กรุณาตอบ yes หรือ no\nSelect> ")

    def _extract_target(self, text: str) -> str:
        m = _TARGET_RE.search(text)
        return m.group(1) if m else AUTHORIZED_SCOPE

    # ------------------------------------------------------------------
    # LLM translation (llm CLI + llm-tools-nmap) — never executes directly
    # ------------------------------------------------------------------

    def _translate_and_preview(self, user_text: str):
        via = "local model" if self.mode == "plain" else AI_MODE_PROVIDERS[self.provider]["label"]
        self._append(f"\n[…] กำลังแปลงคำสั่งผ่าน llm CLI ({via})...\n")

        self._pending_target = self._extract_target(user_text)
        self._pending_user_text = user_text

        argv = ["llm"]
        env = QProcessEnvironment.systemEnvironment()

        if self.mode == "ai":
            cfg = AI_MODE_PROVIDERS[self.provider]
            key = self.key_manager.get_key(self.provider)
            if not key:
                self._append("[!] ไม่พบ API key กรุณาตั้งค่าใหม่\n")
                self._show_provider_select()
                return
            env.insert(cfg["env_var"], key)  # temp env var for this subprocess only
            # System prompt is attached on EVERY AI Mode call — never let
            # the model see raw input without this scoping guard.
            argv += ["-s", SYSTEM_PROMPT]
            argv += ["--functions", LLM_TOOLS_NMAP_PATH, user_text, "-m", cfg["model"]]
        else:
            argv += ["--functions", LLM_TOOLS_NMAP_PATH, user_text]

        proc = QProcess(self)
        proc.setProcessEnvironment(env)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._translate_proc = proc
        proc.finished.connect(self._on_translate_finished)
        proc.errorOccurred.connect(self._on_translate_error)
        proc.start(argv[0], argv[1:])

    def _on_translate_error(self, error):
        self._append(
            f"\n[!] ไม่สามารถเรียก llm CLI ได้ ({error}) — "
            "ตรวจสอบว่าติดตั้ง 'llm' และ 'llm-tools-nmap' แล้ว\n\n>"
        )
        self._translate_proc = None
        self.state = LLMState.READY

    def _on_translate_finished(self, exit_code, exit_status):
        proc = self._translate_proc
        self._translate_proc = None
        if proc is None:
            return
        output = bytes(proc.readAllStandardOutput()).decode(errors="replace")

        ok, result = validate_ai_response(output)
        if not ok:
            self._append(
                f"\n[llm output]\n{result}\n"
                "[i] คำตอบนี้ไม่ใช่คำสั่ง nmap/masscan ที่ถูกต้อง — "
                "แสดงเป็นข้อมูลเท่านั้น ไม่ส่งต่อ Confirmation Gate\n\n>"
            )
            self.state = LLMState.READY
            return
        candidate = result

        # nmap_os_detection (-O) needs root/admin privilege — warn every time,
        # regardless of channel (Plain or AI).
        extra_impact = None
        if re.search(r"(?:^|\s)-O(?:\s|$)", candidate):
            extra_impact = (
                "[!] คำสั่งนี้ใช้ OS detection (-O) ซึ่งต้องรันด้วยสิทธิ์ root/admin "
                "หากรันโดยไม่มีสิทธิ์สูงพอ nmap จะ scan ไม่สำเร็จหรือได้ผลลัพธ์ไม่ถูกต้อง"
            )

        # Reuse the exact same Confirmation Gate as Wizard Console / manual mode.
        self.gate = ConfirmationGate(channel=self.mode, provider=self.provider)
        result = self.gate.request(candidate, self._pending_target, extra_impact=extra_impact)
        if not result.ok:
            self._append(f"\n{result.message}\n\n>")
            self.state = LLMState.READY
            return

        self._append(f"\n{result.preview_box}\n")
        self.state = LLMState.CONFIRM

    # ------------------------------------------------------------------
    # Confirmation Gate — only an exact "yes" reaches QProcess execution
    # ------------------------------------------------------------------

    def _handle_confirmation(self, text: str):
        reply = text.strip()
        if self.gate.confirm(reply):
            self._append("\n[✓] ยืนยันแล้ว กำลังรันคำสั่ง...\n\n")
            self._run_command(self.gate.argv)
        else:
            self.gate.cancel(reply)
            self._append("\n[x] ยกเลิกคำสั่งแล้ว\n\n>")
            self.state = LLMState.READY

    def _run_command(self, argv: List[str]):
        self.state = LLMState.RUNNING
        self._exec_output_buf = []
        proc = QProcess(self)
        self._exec_proc = proc
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_exec_output)
        proc.finished.connect(self._on_exec_finished)
        proc.errorOccurred.connect(self._on_exec_error)
        proc.start(argv[0], argv[1:])
        self.commandEntered.emit(" ".join(argv))

    def _on_exec_output(self):
        if not self._exec_proc:
            return
        chunk = bytes(self._exec_proc.readAllStandardOutput()).decode(errors="replace")
        self._exec_output_buf.append(chunk)
        self._append(chunk)

    def _on_exec_error(self, error):
        self._append(f"\n[!] เกิดข้อผิดพลาดขณะรันคำสั่ง: {error}\n\n>")
        self._exec_proc = None
        self.state = LLMState.READY

    def _on_exec_finished(self, exit_code, exit_status):
        if self.gate:
            self.gate.mark_executed_result(exit_code)
        full_output = "".join(self._exec_output_buf)
        self._exec_proc = None
        self._append(f"\n\n[เสร็จสิ้น, exit code {exit_code}]\n")
        self._append_summary(full_output)
        self.state = LLMState.READY
        self._append("\n>")

    # ------------------------------------------------------------------
    # Post-scan summary
    # ------------------------------------------------------------------

    def _append_summary(self, output: str):
        open_ports = re.findall(r"(\d+)/tcp\s+open", output)

        if self.mode != "ai" or not self.provider:
            if open_ports:
                self._append(f"[Summary] พบ {len(open_ports)} port ที่เปิดอยู่: {', '.join(open_ports)}\n")
            else:
                self._append("[Summary] ไม่พบ port ที่เปิดอยู่ในผลลัพธ์\n")
            return

        # AI Mode: ask the same llm CLI to produce a natural-language summary.
        self._append("[…] กำลังสรุปผลด้วย AI...\n")
        cfg = AI_MODE_PROVIDERS[self.provider]
        key = self.key_manager.get_key(self.provider)
        if not key:
            if open_ports:
                self._append(f"[Summary] พบ {len(open_ports)} port ที่เปิดอยู่: {', '.join(open_ports)}\n")
            return

        env = QProcessEnvironment.systemEnvironment()
        env.insert(cfg["env_var"], key)

        proc = QProcess(self)
        proc.setProcessEnvironment(env)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._summary_proc = proc
        proc.finished.connect(self._on_summary_finished)
        prompt = f"สรุปผลลัพธ์ nmap ต่อไปนี้เป็นภาษาไทยแบบสั้นกระชับ:\n{output[:4000]}"
        proc.start("llm", ["-s", SYSTEM_PROMPT, "-m", cfg["model"], prompt])

    def _on_summary_finished(self, exit_code, exit_status):
        proc = self._summary_proc
        self._summary_proc = None
        if proc is None:
            return
        text = bytes(proc.readAllStandardOutput()).decode(errors="replace").strip()
        if text:
            self._append(f"[AI Summary]\n{text}\n")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        for proc in (self._translate_proc, self._exec_proc, self._summary_proc):
            if proc and proc.state() != QProcess.ProcessState.NotRunning:
                proc.terminate()
        super().closeEvent(event)
