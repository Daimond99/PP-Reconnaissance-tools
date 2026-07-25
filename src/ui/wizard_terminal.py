"""
Wizard Console — scripted, gated nmap wizard (terminal-styled, not a shell).

Unlike `InteractiveTerminal` (a real bash/WSL shell with zero validation),
this widget never spawns an arbitrary shell. It only ever prompts the user
through a fixed sequence of questions (target -> scan profile -> confirm),
same shape as the classic Hydra CLI wizard, and the only process it ever
executes is a single `nmap` invocation that has passed:

    validate_target -> is_target_in_scope -> validate_custom_nmap_flags
        -> build_nmap_command -> ConfirmationGate (impact preview + exact "yes")

This is a first working slice of the planned nmap -> ... -> Evil-WinRM chain
(docs/PROGRESS.md). Only nmap has a real builder/validator/parser/analyzer
right now (see docs/CURRENT_STATE.md) so the "next stage" prompt after a scan
reports the other tools as not-yet-implemented instead of silently doing
nothing.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QProcess
from PySide6.QtGui import QFont, QTextCursor, QKeyEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PySide6.QtCore import Qt

from src.config import AUTHORIZED_SCOPE, CONSOLE_BG, CONSOLE_TEXT
from src.core.confirmation_gate import ConfirmationGate
from src.tools.hydra.analyzer import generate_impact_description as hydra_impact
from src.tools.hydra.builder import HydraSpec, build_hydra_argv, build_hydra_command
from src.tools.hydra.parser import parse_hydra_results
from src.tools.hydra.validator import (
    validate_extra,
    validate_login_field,
    validate_password_field,
    validate_service,
)
from src.tools.nmap.analyzer import recommend_next_tools
from src.tools.nmap.builder import build_nmap_command
from src.tools.nmap.parser import parse_open_ports
from src.tools.nmap.validator import validate_custom_nmap_flags
from src.validation.common import validate_target

BANNER = (
    "TheRecon — Nmap Wizard\n"
    f"Authorized scope: {AUTHORIZED_SCOPE}\n"
    "Every scan goes through scope check + human confirmation before it runs.\n"
)

PROFILES = [
    ("Quick scan", ["-F", "--open"], False),
    ("Stealth SYN scan", ["-sS", "-T2", "--open"], False),
    ("Service/version detection", ["-sV", "--open"], False),
    ("Aggressive (OS + scripts + traceroute)", ["-A", "-T4"], True),
    ("Custom flags (manual entry)", None, None),
]

STATE_TARGET = "target"
STATE_PROFILE = "profile"
STATE_CUSTOM_FLAGS = "custom_flags"
STATE_CONFIRM = "confirm"
STATE_RUNNING = "running"
STATE_NEXT_STAGE = "next_stage"
STATE_HYDRA_LOGIN = "hydra_login"
STATE_HYDRA_PASSWORD = "hydra_password"
STATE_HYDRA_EXTRA = "hydra_extra"
STATE_HYDRA_CONFIRM = "hydra_confirm"
STATE_HYDRA_RUNNING = "hydra_running"


class WizardTerminal(QWidget):
    """State-machine wizard: prompts drive validation/builder/ConfirmationGate.
    No shell is ever spawned; the only subprocess run is the confirmed nmap
    command itself."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc: Optional[QProcess] = None
        self._scan_output = ""
        self._recommendations: List[dict] = []
        self._hydra_output = ""
        self._hydra: dict = {}          # collected inputs for the current hydra run
        self._input_start = 0
        self._target = ""
        self._pending_flags: List[str] = []
        self._pending_intrusive = False
        self._out_of_scope = False
        self._gate: Optional[ConfirmationGate] = None
        self._state = STATE_TARGET

        self._build()
        self._reset_wizard()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.output = QTextEdit()
        self.output.setReadOnly(False)
        self.output.setAcceptRichText(False)
        self.output.setFont(font)
        self.output.setStyleSheet(f"""
            background-color: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border: none; padding: 14px 16px;
            font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;
        """)
        self.output.installEventFilter(self)
        layout.addWidget(self.output, 1)

    # --------------------------------------------------------------- helpers
    def _append(self, text: str) -> None:
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._input_start = cursor.position()
        self.output.setTextCursor(cursor)
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _prompt(self, text: str) -> None:
        self._append(text)

    def _current_input(self) -> str:
        cursor = self.output.textCursor()
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        return cursor.selectedText()

    def _reset_wizard(self) -> None:
        self._target = ""
        self._pending_flags = []
        self._pending_intrusive = False
        self._out_of_scope = False
        self._gate = None
        self._state = STATE_TARGET
        self._append("\n" + BANNER + "\n")
        self._prompt("Target (IP/CIDR/hostname): ")

    # ----------------------------------------------------------- key events
    def eventFilter(self, obj, event):
        if obj is self.output and event.type() == event.Type.KeyPress:
            return self._handle_key(event)
        return super().eventFilter(obj, event)

    def _handle_key(self, event: QKeyEvent) -> bool:
        cursor = self.output.textCursor()
        key = event.key()

        if self._state in (STATE_RUNNING, STATE_HYDRA_RUNNING):
            return True  # input locked while a scan/attack is in flight

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._submit_line()
            return True
        if key in (Qt.Key_Backspace, Qt.Key_Left) and cursor.position() <= self._input_start:
            return True
        if key == Qt.Key_Home:
            cursor.setPosition(
                self._input_start,
                QTextCursor.MoveMode.KeepAnchor if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                else QTextCursor.MoveMode.MoveAnchor,
            )
            self.output.setTextCursor(cursor)
            return True
        if cursor.position() < self._input_start or (
            cursor.hasSelection() and cursor.selectionStart() < self._input_start
        ):
            cursor.setPosition(self._input_start)
            self.output.setTextCursor(cursor)
        return False

    def _submit_line(self) -> None:
        line = self._current_input().strip()
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n")
        self.output.setTextCursor(cursor)
        self._input_start = cursor.position()
        self._dispatch(line)

    # --------------------------------------------------------- state machine
    def _dispatch(self, line: str) -> None:
        if self._state == STATE_TARGET:
            self._handle_target(line)
        elif self._state == STATE_PROFILE:
            self._handle_profile(line)
        elif self._state == STATE_CUSTOM_FLAGS:
            self._handle_custom_flags(line)
        elif self._state == STATE_CONFIRM:
            self._handle_confirm(line)
        elif self._state == STATE_NEXT_STAGE:
            self._handle_next_stage(line)
        elif self._state == STATE_HYDRA_LOGIN:
            self._handle_hydra_login(line)
        elif self._state == STATE_HYDRA_PASSWORD:
            self._handle_hydra_password(line)
        elif self._state == STATE_HYDRA_EXTRA:
            self._handle_hydra_extra(line)
        elif self._state == STATE_HYDRA_CONFIRM:
            self._handle_hydra_confirm(line)

    @staticmethod
    def _looks_like_broken_ip(target: str) -> bool:
        """A dotted all-numeric token (no letters) that isn't a valid IPv4 —
        e.g. '192.168.182235' (missing a dot). validate_target's hostname
        branch would otherwise wave it through and nmap fails to resolve it."""
        import ipaddress
        core = target.split("/")[0].split("-")[0]
        if not core or any(ch.isalpha() for ch in core):
            return False
        if set(core) <= set("0123456789"):  # a bare number, not a dotted IP
            return False
        try:
            ipaddress.ip_address(core)
            return False
        except ValueError:
            return True

    def _handle_target(self, line: str) -> None:
        ok, msg = validate_target(line)
        if not ok:
            self._append(f"[!] {msg}\n")
            self._prompt("Target (IP/CIDR/hostname): ")
            return
        if self._looks_like_broken_ip(msg):
            self._append(
                f"[!] '{msg}' looks like a malformed IP address "
                "(e.g. a missing dot). Enter a valid IP like 192.168.1.50.\n"
            )
            self._prompt("Target (IP/CIDR/hostname): ")
            return

        target = msg
        from src.tools.nmap.analyzer import is_target_in_scope
        in_scope, err = is_target_in_scope(target, AUTHORIZED_SCOPE)
        self._out_of_scope = not in_scope
        if not in_scope:
            # Not a hard block: the human confirmation gate is the real
            # authorization step. Warn loudly here and again in the confirm
            # box, but let the operator scan a target on their own network.
            self._append(
                f"[!] WARNING: {target} is OUTSIDE the authorized scope "
                f"({AUTHORIZED_SCOPE}).\n"
                "    Only continue if you are authorized to test this target.\n"
            )

        self._target = target
        self._append("\nSelect a scan profile:\n")
        for idx, (label, _flags, intrusive) in enumerate(PROFILES, start=1):
            tag = " [!] intrusive" if intrusive else ""
            self._append(f"  {idx}) {label}{tag}\n")
        self._state = STATE_PROFILE
        self._prompt(f"Choice [1-{len(PROFILES)}]: ")

    def _handle_profile(self, line: str) -> None:
        try:
            idx = int(line.strip())
            label, flags, intrusive = PROFILES[idx - 1]
        except (ValueError, IndexError):
            self._append(f"[!] Enter a number from 1 to {len(PROFILES)}.\n")
            self._prompt(f"Choice [1-{len(PROFILES)}]: ")
            return

        if flags is None:  # custom flags
            self._state = STATE_CUSTOM_FLAGS
            self._prompt("Enter nmap flags (whitelisted only): ")
            return

        self._pending_intrusive = intrusive
        self._go_to_confirm(flags)

    def _handle_custom_flags(self, line: str) -> None:
        ok, msg = validate_custom_nmap_flags(line)
        if not ok:
            self._append(f"[!] {msg}\n")
            self._prompt("Enter nmap flags (whitelisted only): ")
            return
        self._pending_intrusive = False
        self._go_to_confirm(msg.split())

    def _go_to_confirm(self, flags: List[str]) -> None:
        command = build_nmap_command(flags, self._target)
        self._gate = ConfirmationGate(channel="wizard")
        warnings = []
        if self._pending_intrusive:
            warnings.append(
                "[!] Custom/aggressive profile — confirm this is against an authorized lab target."
            )
        if self._out_of_scope:
            warnings.append(
                f"[!] TARGET OUT OF SCOPE ({AUTHORIZED_SCOPE}) — proceed only if authorized."
            )
        extra = "\n              ".join(warnings) if warnings else None
        # skip_scope: the wizard already surfaced the out-of-scope warning
        # above and in this box; the exact-"yes" gate stays the enforcement.
        result = self._gate.request(
            command, self._target, extra_impact=extra, skip_scope=True
        )
        if not result.ok:
            self._append(f"\n{result.message}\n")
            self._reset_wizard()
            return
        self._append("\n" + result.preview_box + "\n")
        self._state = STATE_CONFIRM
        self._prompt('Type "yes" to run, anything else cancels: ')

    def _handle_confirm(self, line: str) -> None:
        gate = self._gate
        if gate and gate.confirm(line):
            self._append("\n[+] Confirmed — running nmap...\n")
            self._run_scan(gate.argv)
        else:
            if gate:
                gate.cancel(line or "cancelled")
            self._append("\n[x] Cancelled.\n")
            self._reset_wizard()

    def _run_scan(self, argv: List[str]) -> None:
        self._state = STATE_RUNNING
        self._scan_output = ""
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_scan_output)
        self._proc.finished.connect(self._on_scan_finished)
        self._proc.errorOccurred.connect(self._on_scan_error)
        self._proc.start(argv[0], argv[1:])

    def _read_scan_output(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self._scan_output += data
            self._append(data)

    def _on_scan_error(self, error) -> None:
        self._append(f"\n[!] Failed to run nmap ({error}). Is nmap installed and on PATH?\n")
        self._reset_wizard()

    def _on_scan_finished(self, exit_code: int, _status) -> None:
        if self._gate:
            self._gate.mark_executed_result(exit_code)
        ports = parse_open_ports(self._scan_output)
        if not ports:
            self._append(
                f"\n[+] Scan finished (exit {exit_code}) — no open ports found "
                "(host may be down, filtered, or the target was unreachable).\n"
            )
            self._append("\nStart another scan.\n")
            self._reset_wizard()
            return

        self._append(f"\n[+] Scan finished (exit {exit_code}) — {len(ports)} open port(s):\n")
        for p in ports:
            self._append(f"    {p['port']}/{p['protocol']}  {p['service']}\n")

        # Map the actual open ports to next-stage tools (resource-driven).
        self._recommendations = recommend_next_tools(ports)
        if not self._recommendations:
            self._append(
                "\n[i] None of the open ports map to a known next-stage tool yet. "
                "Start another scan.\n"
            )
            self._reset_wizard()
            return

        self._append("\nOpen ports suggest these next steps in the chain:\n")
        for idx, rec in enumerate(self._recommendations, start=1):
            self._append(
                f"  {idx}) {rec['port']}/{rec['protocol']} {rec['service']} "
                f"→ {rec['tool']} ({rec['module']}) — {rec['why']}\n"
            )
        self._append("  n) Stop / start a new scan\n")
        self._state = STATE_NEXT_STAGE
        self._prompt(f"Choice [1-{len(self._recommendations)}/n]: ")

    def _handle_next_stage(self, line: str) -> None:
        choice = line.strip().lower()
        if choice in ("n", "no", ""):
            self._reset_wizard()
            return
        try:
            rec = self._recommendations[int(choice) - 1]
        except (ValueError, IndexError):
            self._append(f"[!] Enter 1-{len(self._recommendations)} or n.\n")
            self._prompt(f"Choice [1-{len(self._recommendations)}/n]: ")
            return

        tool = rec["tool"]
        if tool == "hydra":
            self._start_hydra(rec)
            return

        # evil-winrm / ncrack: real builders not implemented yet.
        pkg = tool.replace("-", "_")
        self._append(
            f"\n[chain] {rec['port']}/{rec['service']} → {tool} ({rec['module']})\n"
            f"[TODO] src/tools/{pkg}/builder.py is still a placeholder "
            "(see docs/CURRENT_STATE.md) — this chain stage is not wired up yet. "
            "nmap and hydra are the implemented tools for now.\n"
        )
        self._reset_wizard()

    # ---------------------------------------------------------- hydra stage
    def _start_hydra(self, rec: dict) -> None:
        self._hydra = {
            "target": self._target,
            "service": rec["module"],
            "port": rec["port"],
        }
        ok, service = validate_service(rec["module"])
        if not ok:
            self._append(f"\n[!] {service} — no hydra chain for this service.\n")
            self._reset_wizard()
            return
        self._hydra["service"] = service
        self._append(
            f"\n=== Hydra brute force → {service} on {self._target}:{rec['port']} ===\n"
            "Give a single value or a wordlist file path (contains / or \\).\n"
        )
        self._state = STATE_HYDRA_LOGIN
        self._prompt("Username or userlist file: ")

    def _handle_hydra_login(self, line: str) -> None:
        ok, value, is_file = validate_login_field(line)
        if not ok:
            self._append(f"[!] {value}\n")
            self._prompt("Username or userlist file: ")
            return
        self._hydra["login"] = value
        self._hydra["login_is_file"] = is_file
        self._state = STATE_HYDRA_PASSWORD
        self._prompt("Password or passlist file: ")

    def _handle_hydra_password(self, line: str) -> None:
        ok, value, is_file = validate_password_field(line)
        if not ok:
            self._append(f"[!] {value}\n")
            self._prompt("Password or passlist file: ")
            return
        self._hydra["password"] = value
        self._hydra["password_is_file"] = is_file
        self._state = STATE_HYDRA_EXTRA
        self._prompt('Extra tries — letters n(null)/s(same)/r(reversed), or blank: ')

    def _handle_hydra_extra(self, line: str) -> None:
        ok, value = validate_extra(line)
        if not ok:
            self._append(f"[!] {value}\n")
            self._prompt('Extra tries — n/s/r, or blank: ')
            return
        self._hydra["extra"] = value
        self._go_to_hydra_confirm()

    def _go_to_hydra_confirm(self) -> None:
        h = self._hydra
        spec = HydraSpec(
            target=h["target"], service=h["service"],
            login=h["login"], login_is_file=h["login_is_file"],
            password=h["password"], password_is_file=h["password_is_file"],
            port=h.get("port") or None, extra=h.get("extra", ""),
        )
        self._hydra_spec = spec
        masked_cmd = build_hydra_command(spec, mask_password=True)
        real_argv = build_hydra_argv(spec)

        self._gate = ConfirmationGate(channel="wizard")
        impact = hydra_impact(
            spec.service, spec.target, spec.login_is_file, spec.password_is_file
        )
        result = self._gate.request(
            masked_cmd, spec.target, extra_impact=impact,
            argv_override=real_argv, skip_scope=True,
        )
        if not result.ok:
            self._append(f"\n{result.message}\n")
            self._reset_wizard()
            return
        self._append("\n" + result.preview_box + "\n")
        self._state = STATE_HYDRA_CONFIRM
        self._prompt('Type "yes" to launch hydra, anything else cancels: ')

    def _handle_hydra_confirm(self, line: str) -> None:
        gate = self._gate
        if gate and gate.confirm(line):
            self._append("\n[+] Confirmed — running hydra...\n")
            self._run_hydra(gate.argv)
        else:
            if gate:
                gate.cancel(line or "cancelled")
            self._append("\n[x] Cancelled.\n")
            self._reset_wizard()

    def _run_hydra(self, argv: List[str]) -> None:
        self._state = STATE_HYDRA_RUNNING
        self._hydra_output = ""
        program, args = self._route_command(argv)
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_hydra_output)
        self._proc.finished.connect(self._on_hydra_finished)
        self._proc.errorOccurred.connect(self._on_hydra_error)
        self._proc.start(program, args)

    @staticmethod
    def _route_command(argv: List[str]):
        """hydra has no Windows binary — run it through WSL on Windows."""
        import os
        if os.name == "nt":
            return "wsl.exe", ["-e", *argv]
        return argv[0], argv[1:]

    def _read_hydra_output(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self._hydra_output += data
            self._append(data)

    def _on_hydra_error(self, error) -> None:
        self._append(
            f"\n[!] Failed to run hydra ({error}). "
            "On Windows it runs via WSL — install it with: "
            "wsl sudo apt install hydra\n"
        )
        self._reset_wizard()

    def _on_hydra_finished(self, exit_code: int, _status) -> None:
        if self._gate:
            self._gate.mark_executed_result(exit_code)
        creds = parse_hydra_results(self._hydra_output)
        if creds:
            self._append(f"\n[+] Hydra finished — {len(creds)} valid credential(s) found:\n")
            for c in creds:
                self._append(
                    f"    {c['host']}:{c['port']} {c['service']}  "
                    f"login={c['login']}  password={c['password']}\n"
                )
            self._maybe_offer_winrm(creds)
        else:
            self._append(
                f"\n[+] Hydra finished (exit {exit_code}) — no valid credentials found.\n"
            )
            self._reset_wizard()

    def _maybe_offer_winrm(self, creds: List[dict]) -> None:
        """If creds were found for a WinRM/SMB service, note the next chain
        stage (Evil-WinRM) — not yet executable, builder still a placeholder."""
        c = creds[0]
        self._append(
            "\n[chain] Credentials found — next stage would be Evil-WinRM:\n"
            f"          evil-winrm -i {c['host']} -u {c['login']} -p <password>\n"
            "[TODO] src/tools/evil_winrm/builder.py is still a placeholder — "
            "this stage is not wired up yet.\n"
        )
        self._reset_wizard()

    def stop(self) -> None:
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
