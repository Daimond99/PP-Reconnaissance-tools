"""
Recon Tool - Interactive Wizard Engine
Guided shell state machine (Hydra wizard / msfconsole style).
"""

from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.core.wizard_safety import (
    AUTHORIZED_SCOPE_WARNING,
    audit_log_confirmation,
    build_nmap_command,
    format_confirmation_box,
    generate_impact_description,
    quote_arg,
    validate_custom_nmap_flags,
    validate_exact_confirmation,
    validate_file_path,
    validate_port_range,
    validate_target,
    validate_url,
    validate_username,
    validate_password,
    validate_yes_no,
)

DEMO_TOOL_RESTRICTION_NOTICE = (
    "[!] เครื่องมือนี้ยังไม่เปิดใช้งานในเวอร์ชัน demo ปัจจุบัน\n"
    "    ขณะนี้รองรับเฉพาะ Nmap เท่านั้น"
)

CHAIN_DISABLED_NOTICE = (
    "[i] การ chain ไปยังเครื่องมืออื่น (gobuster/dirb/hydra/evil-winrm) "
    "ถูกปิดใช้งานชั่วคราวในเวอร์ชัน demo — จะรันเฉพาะคำสั่ง nmap เท่านั้น"
)


class AttackType(Enum):
    WEB_SERVERS = "web_servers"
    SSH_SERVERS = "ssh_services"
    WINDOWS_SYSTEMS = "windows_systems"
    DATABASES = "databases"
    FULL_NETWORK = "full_network"
    CUSTOM_SCAN = "custom_scan"


class WizardStep(Enum):
    TOOL_SELECT = "tool_select"
    ATTACK_MENU = "attack_menu"
    TARGET = "target"
    SCAN_LEVEL = "scan_level"
    SUGGESTION = "suggestion"
    SUGGESTION_EDIT = "suggestion_edit"
    WEB_DIR_SCAN = "web_dir_scan"
    WEB_DIR_TOOL = "web_dir_tool"
    WEB_URL = "web_url"
    WEB_WORDLIST = "web_wordlist"
    SSH_PORT_RANGE = "ssh_port_range"
    SSH_BRUTE = "ssh_brute"
    SSH_USERLIST = "ssh_userlist"
    SSH_PASSLIST = "ssh_passlist"
    WIN_WINRM = "win_winrm"
    WIN_USERNAME = "win_username"
    WIN_PASSWORD = "win_password"
    DB_TYPE = "db_type"
    CUSTOM_FLAGS = "custom_flags"
    PREVIEW = "preview"
    EXECUTING = "executing"


# ---------------------------------------------------------------------------
# Scan Level definitions — grouped by AttackType
# Each entry: (id, label, flags_list, reason, is_aggressive)
# ---------------------------------------------------------------------------

ScanLevelDef = Tuple[int, str, List[str], str, bool]


def _scan_levels_for(attack: AttackType) -> List[ScanLevelDef]:
    """Return scan level definitions appropriate for the given attack type."""
    # Stealth group (shared across all)
    stealth: List[ScanLevelDef] = [
        (1, "Stealth SYN scan",               ["-sS", "-T2", "--open"],
         "ส่ง packet แบบ half-open ไม่ครบ handshake ตรวจจับยากกว่า scan ปกติ", False),
        (2, "Fragmented stealth",             ["-sS", "-f", "-T2"],
         "แบ่ง packet เป็นชิ้นเล็กเพื่อหลบ firewall/IDS พื้นฐาน", False),
    ]
    # Verbose group (shared across all)
    verbose: List[ScanLevelDef] = [
        (3, "Verbose service scan",           ["-sV", "-v", "--version-all", "--open"],
         "ดึงข้อมูล service/version ละเอียดที่สุด พร้อมแสดง progress แบบ real-time", False),
        (4, "Verbose + script scan",          ["-sV", "-sC", "-v"],
         "รัน default NSE script ร่วมด้วยเพื่อเก็บข้อมูลเพิ่มเติม เช่น banner, algorithm", False),
    ]

    if attack == AttackType.WEB_SERVERS:
        aggressive: List[ScanLevelDef] = [
            (5, "Aggressive full detect",     ["-A", "-T4"],
             "รวม OS detection, script scan, traceroute ในคำสั่งเดียว ส่ง traffic เยอะและตรวจจับได้ง่ายมาก ใช้เฉพาะ lab/sandbox เท่านั้น", True),
            (6, "Brute-timing critical",      ["-T5", "--open", "-Pn"],
             "scan เร็วสุดขีดและข้าม host discovery (-Pn) อาจทำให้เครือข่ายที่มี IDS/IPS แจ้งเตือนทันที หรือทำให้ target ที่ทรัพยากรจำกัดหน่วงได้", True),
            (7, "Vulnerability script scan",  ["--script", "http-vuln*", "-sV"],
             "รัน NSE script ตรวจสอบช่องโหว่เว็บ อาจส่งผลกระทบต่อ service ที่ไม่เสถียร (บาง script อาจทำให้ service ค้างหรือ crash ได้)", True),
        ]
    elif attack == AttackType.SSH_SERVERS:
        aggressive: List[ScanLevelDef] = [
            (5, "Aggressive full detect",     ["-A", "-T4"],
             "รวม OS detection, script scan, traceroute ในคำสั่งเดียว ส่ง traffic เยอะและตรวจจับได้ง่ายมาก ใช้เฉพาะ lab/sandbox เท่านั้น", True),
            (6, "Brute-timing critical",      ["-T5", "--open", "-Pn"],
             "scan เร็วสุดขีดและข้าม host discovery (-Pn) อาจทำให้เครือข่ายที่มี IDS/IPS แจ้งเตือนทันที หรือทำให้ target ที่ทรัพยากรจำกัดหน่วงได้", True),
            (7, "Vulnerability script scan",  ["--script", "ssh*", "-sV"],
             "รัน NSE script ตรวจสอบช่องโหว่ SSH อาจส่งผลกระทบต่อ service ที่ไม่เสถียร", True),
        ]
    elif attack == AttackType.WINDOWS_SYSTEMS:
        aggressive: List[ScanLevelDef] = [
            (5, "Aggressive full detect",     ["-A", "-T4"],
             "รวม OS detection, script scan, traceroute ในคำสั่งเดียว ส่ง traffic เยอะและตรวจจับได้ง่ายมาก ใช้เฉพาะ lab/sandbox เท่านั้น", True),
            (6, "Brute-timing critical",      ["-T5", "--open", "-Pn"],
             "scan เร็วสุดขีดและข้าม host discovery (-Pn) อาจทำให้เครือข่ายที่มี IDS/IPS แจ้งเตือนทันที หรือทำให้ target ที่ทรัพยากรจำกัดหน่วงได้", True),
            (7, "Vulnerability script scan",  ["--script", "smb-vuln*", "-sV"],
             "รัน NSE script ตรวจสอบช่องโหว่ Windows (SMB) อาจส่งผลกระทบต่อ service ที่ไม่เสถียร", True),
        ]
    elif attack == AttackType.DATABASES:
        aggressive: List[ScanLevelDef] = [
            (5, "Aggressive full detect",     ["-A", "-T4"],
             "รวม OS detection, script scan, traceroute ในคำสั่งเดียว ส่ง traffic เยอะและตรวจจับได้ง่ายมาก ใช้เฉพาะ lab/sandbox เท่านั้น", True),
            (6, "Brute-timing critical",      ["-T5", "--open", "-Pn"],
             "scan เร็วสุดขีดและข้าม host discovery (-Pn) อาจทำให้เครือข่ายที่มี IDS/IPS แจ้งเตือนทันที หรือทำให้ target ที่ทรัพยากรจำกัดหน่วงได้", True),
            (7, "Vulnerability script scan",  ["--script", "ms-sql*", "-sV"],
             "รัน NSE script ตรวจสอบช่องโหว่ DB (MSSQL) อาจส่งผลกระทบต่อ service ที่ไม่เสถียร", True),
        ]
    elif attack == AttackType.FULL_NETWORK:
        aggressive: List[ScanLevelDef] = [
            (5, "Aggressive full detect",     ["-A", "-T4"],
             "รวม OS detection, script scan, traceroute ในคำสั่งเดียว ส่ง traffic เยอะและตรวจจับได้ง่ายมาก ใช้เฉพาะ lab/sandbox เท่านั้น", True),
            (6, "Brute-timing critical",      ["-T5", "--open", "-Pn"],
             "scan เร็วสุดขีดและข้าม host discovery (-Pn) อาจทำให้เครือข่ายที่มี IDS/IPS แจ้งเตือนทันที หรือทำให้ target ที่ทรัพยากรจำกัดหน่วงได้", True),
            (7, "Vulnerability script scan",  ["--script", "vuln", "-sV"],
             "รัน NSE script ตรวจสอบช่องโหว่ทั่วไป อาจส่งผลกระทบต่อ service ที่ไม่เสถียร (บาง script อาจทำให้ service ค้างหรือ crash ได้)", True),
        ]
    else:
        aggressive = []

    return stealth + verbose + aggressive


def _get_base_ports_for(attack: AttackType) -> str:
    """Return the default port list for the given attack type."""
    mapping = {
        AttackType.WEB_SERVERS: "80,443,8080,8443",
        AttackType.SSH_SERVERS: "22",
        AttackType.WINDOWS_SYSTEMS: "445,3389,5985",
        AttackType.DATABASES: "1433,3306,5432,27017",
        AttackType.FULL_NETWORK: "",
    }
    return mapping.get(attack, "")


# ---------------------------------------------------------------------------


@dataclass
class WizardState:
    """Current wizard session: step, choices, and assembled command chain."""

    current_step: WizardStep = WizardStep.TOOL_SELECT
    selected_tool: Optional[str] = None
    attack_type: Optional[AttackType] = None
    choices: Dict[str, Any] = field(default_factory=dict)
    command_parts: List[str] = field(default_factory=list)
    step_history: List[WizardStep] = field(default_factory=list)
    # Track the current cancel target for audit logging
    current_cancel_command: str = ""

    def reset_flow(self) -> None:
        self.current_step = WizardStep.TOOL_SELECT
        self.selected_tool = None
        self.attack_type = None
        self.choices.clear()
        self.command_parts.clear()
        self.step_history.clear()
        self.current_cancel_command = ""

    def go_back(self) -> bool:
        if not self.step_history:
            return False
        self.current_step = self.step_history.pop()
        return True

    def advance_to(self, step: WizardStep) -> None:
        self.step_history.append(self.current_step)
        self.current_step = step

    @property
    def command_chain(self) -> str:
        return " && ".join(self.command_parts)

    def rebuild_primary_scan(self) -> None:
        """Rebuild the first scan command from attack type + target + scan level."""
        if not self.attack_type or "target" not in self.choices:
            return

        target = self.choices["target"]
        attack = self.attack_type
        scan_level = self.choices.get("scan_level")

        if scan_level:
            # Use the flags from the selected scan level
            levels = _scan_levels_for(attack)
            level_map = {lid: flags for lid, _name, flags, _reason, _agg in levels}
            flags = level_map.get(scan_level)
            if flags:
                ports = _get_base_ports_for(attack)
                final_flags = list(flags)
                if ports:
                    # Insert -p before any other flags if ports matter
                    final_flags = ["-p", ports] + final_flags
                cmd = build_nmap_command(final_flags, target)
                if self.command_parts:
                    self.command_parts[0] = cmd
                else:
                    self.command_parts.append(cmd)
                return

        # Fallback: original logic
        if attack == AttackType.WEB_SERVERS:
            cmd = build_nmap_command(
                ["-p", "80,443,8080", "-sV", "--script", "http-title,http-headers"],
                target,
            )
        elif attack == AttackType.SSH_SERVERS:
            cmd = build_nmap_command(["-p", "22", "-sV", "--open"], target)
        elif attack == AttackType.WINDOWS_SYSTEMS:
            cmd = build_nmap_command(["-p", "445,3389,5985", "-sV"], target)
        elif attack == AttackType.DATABASES:
            cmd = build_nmap_command(["-p", "1433,3306,5432,27017", "-sV"], target)
        elif attack == AttackType.FULL_NETWORK:
            cmd = build_nmap_command(["-sV", "-O"], target)
        elif attack == AttackType.CUSTOM_SCAN:
            flags = self.choices.get("custom_flags", "-sV")
            cmd = f"nmap {flags} {quote_arg(target)}"
        else:
            cmd = build_nmap_command(["-sV"], target)

        if self.command_parts:
            self.command_parts[0] = cmd
        else:
            self.command_parts.append(cmd)


@dataclass
class WizardResult:
    success: bool
    lines: List[str] = field(default_factory=list)
    prompt: str = "Select>"
    action: Optional[str] = None
    commands: List[str] = field(default_factory=list)


SUGGESTION_REASONS = {
    AttackType.WEB_SERVERS: "สแกน port เว็บที่พบบ่อยที่สุด พร้อมดึงชื่อหน้าเว็บและ header เพื่อระบุเทคโนโลยีที่ใช้",
    AttackType.SSH_SERVERS: "เช็คเฉพาะ port SSH มาตรฐาน และแสดงเฉพาะ host ที่เปิดใช้งานจริง",
    AttackType.WINDOWS_SYSTEMS: "ตรวจ SMB, RDP, WinRM ซึ่งเป็น service หลักที่ Windows มักเปิดใช้",
    AttackType.DATABASES: "ตรวจ MSSQL, MySQL, PostgreSQL, MongoDB port มาตรฐาน",
    AttackType.FULL_NETWORK: "สแกนแบบละเอียดทั้ง service version และ OS detection ครอบคลุมทุก port ที่เปิด",
}


class WizardEngine:
    """Interactive guided wizard with branching attack chains."""

    TOOL_MENU = """WIZARD MODE - Select Tool
{warning}

เลือกเครื่องมือที่จะใช้:

 1. Nmap
 2. Masscan
 3. Hydra
 4. Ncrack
 5. Evil-WinRM
 6. Auto Chain (Recon → Action)

Select option (1-6):"""

    ATTACK_MENU = """WIZARD MODE - Expert Attack Chain Guide
{warning}

What do you want to find?

 1. Web Servers
 2. SSH Services
 3. Windows Systems
 4. Databases
 5. Full Network Scan
 6. Custom Scan

Type: check | install | help | reset | back
Select option (1-6):"""

    DB_OPTIONS = """Select database focus:

 1. Microsoft SQL (1433)
 2. MySQL (3306)
 3. PostgreSQL (5432)
 4. MongoDB (27017)
 5. All common DB ports

Select option (1-5):"""

    def __init__(self) -> None:
        self.state = WizardState()
        self.is_windows = platform.system() == "Windows"
        self._awaiting_confirm = False

    def reset(self) -> WizardResult:
        self.state.reset_flow()
        self._awaiting_confirm = False
        return self._tool_menu_result()

    def go_back(self) -> WizardResult:
        if self.state.go_back():
            self._awaiting_confirm = False
            return self._prompt_for_current_step()
        return self.reset()

    def handle_input(self, user_input: str) -> WizardResult:
        text = user_input.strip()
        step = self.state.current_step

        # Allow empty for SUGGESTION and SCAN_LEVEL (default Enter = accept first)
        if not text and step not in (WizardStep.SUGGESTION, WizardStep.SCAN_LEVEL):
            return WizardResult(False, ["Input cannot be empty."], self._current_prompt())

        lowered = text.lower()
        if lowered in ("check", "install", "help", "reset", "back", "cancel"):
            return self._handle_meta_command(lowered)

        if self._awaiting_confirm:
            return self._handle_confirm(text)

        handlers: Dict[WizardStep, Callable[[str], WizardResult]] = {
            WizardStep.TOOL_SELECT: self._handle_tool_select,
            WizardStep.ATTACK_MENU: self._handle_attack_menu,
            WizardStep.TARGET: self._handle_target,
            WizardStep.SCAN_LEVEL: self._handle_scan_level,
            WizardStep.SUGGESTION: self._handle_suggestion,
            WizardStep.SUGGESTION_EDIT: self._handle_suggestion_edit,
            WizardStep.WEB_DIR_SCAN: self._handle_web_dir_scan,
            WizardStep.WEB_DIR_TOOL: self._handle_web_dir_tool,
            WizardStep.WEB_URL: self._handle_web_url,
            WizardStep.WEB_WORDLIST: self._handle_web_wordlist,
            WizardStep.SSH_PORT_RANGE: self._handle_ssh_port_range,
            WizardStep.SSH_BRUTE: self._handle_ssh_brute,
            WizardStep.SSH_USERLIST: self._handle_ssh_userlist,
            WizardStep.SSH_PASSLIST: self._handle_ssh_passlist,
            WizardStep.WIN_WINRM: self._handle_win_winrm,
            WizardStep.WIN_USERNAME: self._handle_win_username,
            WizardStep.WIN_PASSWORD: self._handle_win_password,
            WizardStep.DB_TYPE: self._handle_db_type,
            WizardStep.CUSTOM_FLAGS: self._handle_custom_flags,
            WizardStep.PREVIEW: self._handle_preview_choice,
        }
        handler = handlers.get(step)
        if handler is None:
            return WizardResult(False, ["Wizard is busy or in an unknown state."], self._current_prompt())
        return handler(text)

    def _handle_meta_command(self, cmd: str) -> WizardResult:
        if cmd == "reset":
            return self.reset()
        if cmd == "back":
            return self.go_back()
        if cmd == "check":
            return WizardResult(True, ["__SHOW_TOOL_STATUS__"], self._current_prompt())
        if cmd == "install":
            return WizardResult(True, ["__SHOW_INSTALL_GUIDE__"], self._current_prompt())
        if cmd == "help":
            return WizardResult(True, [self._help_text()], self._current_prompt())
        if cmd == "cancel" and self.state.current_step == WizardStep.EXECUTING:
            return WizardResult(True, ["Cancelling running process..."], action="cancel")
        return WizardResult(False, ["Nothing to cancel."], self._current_prompt())

    def _handle_tool_select(self, text: str) -> WizardResult:
        mapping = {
            "1": "nmap",
            "2": "masscan",
            "3": "hydra",
            "4": "ncrack",
            "5": "evil-winrm",
        }
        if text == "6":
            # TODO: Auto Chain (Recon → Action)
            # This is a placeholder for future implementation.
            # auto_chain_wizard() will be implemented to automatically select
            # tools and chain them together based on scan results.
            return WizardResult(
                False,
                [DEMO_TOOL_RESTRICTION_NOTICE, "",
                 self.TOOL_MENU.format(warning=AUTHORIZED_SCOPE_WARNING)],
                "Select>",
            )

        if text not in mapping:
            return WizardResult(
                False,
                [f"Invalid selection: {text}", "Select option (1-6):"],
                "Select>",
            )

        tool = mapping[text]
        if tool != "nmap":
            # Do NOT advance the flow — loop back to the same tool menu.
            return WizardResult(
                False,
                [DEMO_TOOL_RESTRICTION_NOTICE, "", self.TOOL_MENU.format(warning=AUTHORIZED_SCOPE_WARNING)],
                "Select>",
            )

        self.state.selected_tool = tool
        self.state.advance_to(WizardStep.ATTACK_MENU)
        return self._menu_result()

    # TODO: auto_chain_wizard() - Future implementation for Auto Chain mode.
    # This function will:
    # 1. Run an initial broad scan (nmap/masscan)
    # 2. Parse results to detect open ports and services
    # 3. Automatically propose follow-up tools (hydra for SSH, evil-winrm for WinRM, etc.)
    # 4. Chain multiple tools together in a single workflow
    def auto_chain_wizard(self) -> WizardResult:
        """Placeholder for Auto Chain (Recon → Action) logic."""
        # TODO: implement full auto-chain logic
        return WizardResult(
            False,
            [DEMO_TOOL_RESTRICTION_NOTICE],
            "Select>",
        )

    def _handle_attack_menu(self, text: str) -> WizardResult:
        mapping = {
            "1": AttackType.WEB_SERVERS,
            "2": AttackType.SSH_SERVERS,
            "3": AttackType.WINDOWS_SYSTEMS,
            "4": AttackType.DATABASES,
            "5": AttackType.FULL_NETWORK,
            "6": AttackType.CUSTOM_SCAN,
        }
        if text not in mapping:
            return WizardResult(
                False,
                [f"Invalid selection: {text}", "Select option (1-6):"],
                "Select>",
            )

        attack = mapping[text]
        self.state.attack_type = attack
        self.state.advance_to(WizardStep.TARGET)
        label = attack.value.replace("_", " ").title()
        return WizardResult(
            True,
            [f"\n[+] Selected: {label}", self._target_prompt()],
            "Input>",
        )

    def _handle_target(self, text: str) -> WizardResult:
        ok, result = validate_target(text)
        if not ok:
            return WizardResult(False, [result, self._target_prompt()], "Input>")

        self.state.choices["target"] = result

        attack = self.state.attack_type
        if attack == AttackType.CUSTOM_SCAN:
            self.state.advance_to(WizardStep.CUSTOM_FLAGS)
            return WizardResult(
                True,
                [
                    f"[+] Target set: {result}",
                    "",
                    "Enter custom nmap flags (no ; | & allowed):",
                    "Example: -sS -p 22,80,443 --open -sV",
                ],
                "Input>",
            )

        # For all non-custom scans, offer scan level selection
        self.state.advance_to(WizardStep.SCAN_LEVEL)
        return self._render_scan_level_menu([f"[+] Target set: {result}"])

    def _render_scan_level_menu(self, prefix_lines: List[str]) -> WizardResult:
        """Build the scan level choice menu for the current attack type."""
        attack = self.state.attack_type
        if not attack:
            return self._goto_suggestion(prefix_lines)

        levels = _scan_levels_for(attack)
        label = attack.value.replace("_", " ").title()

        lines = list(prefix_lines)
        lines.append("")
        lines.append(f"[Wizard] เลือกระดับการสแกนสำหรับ {label}:")
        lines.append("")

        # Group by category
        current_section = ""
        for lid, name, _flags, reason, is_agg in levels:
            if lid == 1:
                current_section = " -- Stealth --"
                lines.append(current_section)
            elif lid == 3 and current_section != " -- Stealth --":
                current_section = " -- Verbose / Info Gathering --"
                lines.append(current_section)
            elif lid == 5 and current_section != " -- Verbose / Info Gathering --":
                current_section = " -- Aggressive / Critical (ใช้ด้วยความระมัดระวัง) --"
                lines.append(current_section)

            warning_mark = "⚠ " if is_agg else ""
            lines.append(f" {lid}. {warning_mark}{name}")
            lines.append(f"    เหตุผล: {reason}")
            lines.append("")

        lines.append("Select scan level (1-7):")
        return WizardResult(True, lines, "Level>")

    def _handle_scan_level(self, text: str) -> WizardResult:
        """Handle scan level selection."""
        attack = self.state.attack_type
        if not attack:
            return self._goto_suggestion([])

        levels = _scan_levels_for(attack)
        valid_ids = {str(lid) for lid, _name, _flags, _reason, _agg in levels}

        choice = text.strip()
        if choice not in valid_ids:
            return WizardResult(
                False,
                [f"Invalid selection: {choice}",
                 "Select scan level (1-7):"],
                "Level>",
            )

        self.state.choices["scan_level"] = int(choice)
        self.state.rebuild_primary_scan()

        # Find the name of the selected level for messaging
        level_name = ""
        is_aggressive = False
        for lid, name, _flags, _reason, agg in levels:
            if lid == int(choice):
                level_name = name
                is_aggressive = agg
                break

        prefix = [f"[+] Scan level selected: {level_name}"]
        if is_aggressive:
            prefix.append("⚠ คำเตือน: คุณเลือกระดับการสแกนเชิงรุก กรุณาตรวจสอบให้แน่ใจว่าได้รับอนุญาตแล้ว")

        return self._goto_suggestion(prefix)

    def _goto_suggestion(self, prefix_lines: List[str]) -> WizardResult:
        self.state.advance_to(WizardStep.SUGGESTION)
        attack = self.state.attack_type
        label = attack.value.replace("_", " ").title()
        reason = SUGGESTION_REASONS.get(attack, "")
        cmd = self.state.command_parts[0]
        lines = prefix_lines + [
            "",
            f"[Wizard] แนะนำคำสั่งนี้สำหรับ {label}:",
            f" {cmd}",
            "",
            f' เหตุผล: "{reason}"',
            "",
            "พิมพ์ Enter เพื่อใช้คำสั่งนี้ หรือพิมพ์ 'edit' เพื่อแก้ไข port/flag เอง",
        ]
        return WizardResult(True, lines, "Wizard>")

    def _handle_suggestion(self, text: str) -> WizardResult:
        choice = text.strip().lower()
        if choice == "edit":
            self.state.advance_to(WizardStep.SUGGESTION_EDIT)
            return WizardResult(
                True,
                [
                    "แก้ไข port/flag สำหรับคำสั่ง nmap นี้ (no ; | & allowed):",
                    "Example: -p 22,80,443 -sV --open",
                ],
                "Input>",
            )
        # Empty Enter (or anything else) accepts the auto-suggested command as-is.
        return self._goto_preview([f"[+] ใช้คำสั่งที่แนะนำ: {self.state.command_parts[0]}"])

    def _handle_suggestion_edit(self, text: str) -> WizardResult:
        ok, flags = validate_custom_nmap_flags(text)
        if not ok:
            return WizardResult(False, [flags, "แก้ไข port/flag:"], "Input>")

        target = self.state.choices["target"]
        cmd = f"nmap {flags} {quote_arg(target)}"
        if self.state.command_parts:
            self.state.command_parts[0] = cmd
        else:
            self.state.command_parts.append(cmd)
        return self._goto_preview([f"[+] คำสั่งที่แก้ไขแล้ว: {cmd}"])

    def _handle_web_dir_scan(self, text: str) -> WizardResult:
        ok, yes, err = validate_yes_no(text)
        if not ok:
            return WizardResult(False, [err, "Run directory brute-force? [y/n]:"], "Select>")

        self.state.choices["web_dir_scan"] = yes
        if not yes:
            return self._goto_preview(["[+] Skipping directory enumeration."])

        if not self._tool_available("gobuster") and not self._tool_available("dirb"):
            return self._goto_preview(
                [
                    "[!] Neither gobuster nor dirb is installed.",
                    "[+] Continuing with nmap scan only.",
                ]
            )

        self.state.advance_to(WizardStep.WEB_DIR_TOOL)
        lines = ["Select directory tool:", " 1. gobuster", " 2. dirb"]
        if self._tool_available("gobuster"):
            lines.append("    (gobuster detected)")
        else:
            lines.append("    (gobuster NOT installed)")
        if self._tool_available("dirb"):
            lines.append("    (dirb detected)")
        else:
            lines.append("    (dirb NOT installed)")
        lines.append("")
        lines.append("Select option (1-2):")
        return WizardResult(True, lines, "Select>")

    def _handle_web_dir_tool(self, text: str) -> WizardResult:
        if text == "1":
            if not self._tool_available("gobuster"):
                return WizardResult(False, ["gobuster is not installed.", "Select option (1-2):"], "Select>")
            self.state.choices["web_dir_tool"] = "gobuster"
        elif text == "2":
            if not self._tool_available("dirb"):
                return WizardResult(False, ["dirb is not installed.", "Select option (1-2):"], "Select>")
            self.state.choices["web_dir_tool"] = "dirb"
        else:
            return WizardResult(False, [f"Invalid selection: {text}", "Select option (1-2):"], "Select>")

        self.state.advance_to(WizardStep.WEB_URL)
        return WizardResult(
            True,
            [f"[+] Tool: {self.state.choices['web_dir_tool']}", "", "Target URL (e.g. http://192.168.1.1):"],
            "Input>",
        )

    def _handle_web_url(self, text: str) -> WizardResult:
        ok, url = validate_url(text)
        if not ok:
            return WizardResult(False, [url, "Target URL:"], "Input>")
        self.state.choices["web_url"] = url
        self.state.advance_to(WizardStep.WEB_WORDLIST)
        default = (
            r"C:\tools\wordlists\common.txt"
            if self.is_windows
            else "/usr/share/wordlists/dirb/common.txt"
        )
        return WizardResult(
            True,
            [f"[+] URL: {url}", "", f"Wordlist path (default: {default}):"],
            "Input>",
        )

    def _handle_web_wordlist(self, text: str) -> WizardResult:
        default = (
            r"C:\tools\wordlists\common.txt"
            if self.is_windows
            else "/usr/share/wordlists/dirb/common.txt"
        )
        wordlist = text.strip() or default
        ok, path = validate_file_path(wordlist)
        if not ok:
            return WizardResult(False, [path, "Wordlist path:"], "Input>")

        self.state.choices["web_wordlist"] = path
        tool = self.state.choices["web_dir_tool"]
        url = self.state.choices["web_url"]
        if tool == "gobuster":
            follow = f"gobuster dir -u {quote_arg(url)} -w {quote_arg(path)}"
        else:
            follow = f"dirb {quote_arg(url)} {quote_arg(path)}"
        self.state.command_parts.append(follow)
        return self._goto_preview([f"[+] Follow-up queued: {follow}"])

    def _handle_ssh_port_range(self, text: str) -> WizardResult:
        ports = text.strip() or "22"
        ok, result = validate_port_range(ports)
        if not ok:
            return WizardResult(False, [result, "SSH port range:"], "Input>")

        self.state.choices["port_range"] = result
        self.state.rebuild_primary_scan()
        return self._goto_preview(
            [
                f"[+] Port range: {result}",
                f"[+] Updated scan: {self.state.command_parts[0]}",
            ]
        )

    def _handle_ssh_brute(self, text: str) -> WizardResult:
        ok, yes, err = validate_yes_no(text)
        if not ok:
            return WizardResult(False, [err, "Brute-force SSH? [y/n]:"], "Select>")

        self.state.choices["ssh_brute"] = yes
        if not yes:
            return self._goto_preview(["[+] Skipping hydra brute-force."])

        if not self._tool_available("hydra"):
            return self._goto_preview(
                ["[!] hydra is not installed.", "[+] Continuing with nmap scan only."]
            )

        self.state.advance_to(WizardStep.SSH_USERLIST)
        default = (
            r"C:\tools\wordlists\users.txt"
            if self.is_windows
            else "/usr/share/wordlists/metasploit/unix_users.txt"
        )
        return WizardResult(
            True,
            ["", f"Userlist path (default: {default}):"],
            "Input>",
        )

    def _handle_ssh_userlist(self, text: str) -> WizardResult:
        default = (
            r"C:\tools\wordlists\users.txt"
            if self.is_windows
            else "/usr/share/wordlists/metasploit/unix_users.txt"
        )
        path = text.strip() or default
        ok, result = validate_file_path(path)
        if not ok:
            return WizardResult(False, [result, "Userlist path:"], "Input>")

        self.state.choices["ssh_userlist"] = result
        self.state.advance_to(WizardStep.SSH_PASSLIST)
        default_pass = (
            r"C:\tools\wordlists\rockyou.txt"
            if self.is_windows
            else "/usr/share/wordlists/rockyou.txt"
        )
        return WizardResult(True, [f"[+] Userlist: {result}", "", f"Passlist path (default: {default_pass}):"], "Input>")

    def _handle_ssh_passlist(self, text: str) -> WizardResult:
        default = (
            r"C:\tools\wordlists\rockyou.txt"
            if self.is_windows
            else "/usr/share/wordlists/rockyou.txt"
        )
        path = text.strip() or default
        ok, result = validate_file_path(path)
        if not ok:
            return WizardResult(False, [result, "Passlist path:"], "Input>")

        self.state.choices["ssh_passlist"] = result
        target = self.state.choices["target"]
        userlist = self.state.choices["ssh_userlist"]
        follow = (
            f"hydra -L {quote_arg(userlist)} -P {quote_arg(result)} "
            f"ssh://{quote_arg(target)}"
        )
        self.state.command_parts.append(follow)
        return self._goto_preview([f"[+] Hydra chain queued: {follow}"])

    def _handle_win_winrm(self, text: str) -> WizardResult:
        ok, yes, err = validate_yes_no(text)
        if not ok:
            return WizardResult(False, [err, "Use Evil-WinRM? [y/n]:"], "Select>")

        self.state.choices["win_winrm"] = yes
        if not yes:
            return self._goto_preview(["[+] Skipping Evil-WinRM connection."])

        if not self._tool_available("evil-winrm"):
            return self._goto_preview(
                ["[!] evil-winrm is not installed.", "[+] Continuing with nmap scan only."]
            )

        self.state.advance_to(WizardStep.WIN_USERNAME)
        return WizardResult(True, ["", "WinRM username (e.g. Administrator):"], "Input>")

    def _handle_win_username(self, text: str) -> WizardResult:
        ok, user = validate_username(text)
        if not ok:
            return WizardResult(False, [user, "Username:"], "Input>")

        self.state.choices["win_username"] = user
        self.state.advance_to(WizardStep.WIN_PASSWORD)
        return WizardResult(True, [f"[+] Username: {user}", "", "Password:"], "Password>")

    def _handle_win_password(self, text: str) -> WizardResult:
        ok, password = validate_password(text)
        if not ok:
            return WizardResult(False, [password, "Password:"], "Password>")

        self.state.choices["win_password"] = password
        target = self.state.choices["target"]
        user = self.state.choices["win_username"]
        follow = (
            f"evil-winrm -i {quote_arg(target)} -u {quote_arg(user)} "
            f"-p {quote_arg(password)}"
        )
        self.state.command_parts.append(follow)
        return self._goto_preview([f"[+] WinRM chain queued: {follow}"])

    def _handle_db_type(self, text: str) -> WizardResult:
        if text not in {"1", "2", "3", "4", "5"}:
            return WizardResult(False, [f"Invalid selection: {text}", self.DB_OPTIONS], "Select>")
        self.state.choices["db_type"] = text
        self.state.rebuild_primary_scan()
        return self._goto_preview(
            [f"[+] Database scan queued: {self.state.command_parts[0]}"]
        )

    def _handle_custom_flags(self, text: str) -> WizardResult:
        ok, flags = validate_custom_nmap_flags(text)
        if not ok:
            return WizardResult(
                False,
                [flags, "Enter custom nmap flags:"],
                "Input>",
            )
        self.state.choices["custom_flags"] = flags
        self.state.rebuild_primary_scan()
        return self._goto_preview(
            [f"[+] Custom scan queued: {self.state.command_parts[0]}"]
        )

    def _handle_preview_choice(self, text: str) -> WizardResult:
        chain = self.state.command_chain
        target = self.state.choices.get("target", "")
        confirmed = validate_exact_confirmation(text)

        audit_log_confirmation(command=chain, target=target, response=text, executed=confirmed)

        if confirmed:
            self._awaiting_confirm = False
            self.state.advance_to(WizardStep.EXECUTING)
            self.state.current_cancel_command = chain
            return WizardResult(
                True,
                ["", f"[*] Executing: {chain}", "[*] Press Ctrl+C or type 'cancel' to abort.", ""],
                prompt="",
                action="execute",
                commands=list(self.state.command_parts),
            )

        self._awaiting_confirm = False
        return self.reset()

    def _handle_confirm(self, text: str) -> WizardResult:
        return self._handle_preview_choice(text)

    def _goto_preview(self, prefix_lines: List[str]) -> WizardResult:
        self.state.advance_to(WizardStep.PREVIEW)
        self._awaiting_confirm = True
        chain = self.state.command_chain
        target = self.state.choices.get("target", "")
        flags = chain.split(" ")[1:] if chain else []
        impact = generate_impact_description(flags, target) if target else "N/A"
        box = format_confirmation_box(chain, target, impact)
        lines = prefix_lines + ["", box]
        return WizardResult(True, lines, "Confirm>")

    def _prompt_for_current_step(self) -> WizardResult:
        step = self.state.current_step
        if step == WizardStep.TOOL_SELECT:
            return self._tool_menu_result()
        if step == WizardStep.ATTACK_MENU:
            return self._menu_result()
        if step == WizardStep.TARGET:
            return WizardResult(True, [self._target_prompt()], "Input>")
        if step == WizardStep.SCAN_LEVEL:
            return self._render_scan_level_menu([])
        if step == WizardStep.SUGGESTION:
            return self._goto_suggestion([])
        if step == WizardStep.SUGGESTION_EDIT:
            return WizardResult(
                True,
                ["แก้ไข port/flag สำหรับคำสั่ง nmap นี้ (no ; | & allowed):"],
                "Input>",
            )
        if step == WizardStep.WEB_DIR_SCAN:
            return WizardResult(True, ["Run directory brute-force? [y/n]:"], "Select>")
        if step == WizardStep.SSH_PORT_RANGE:
            return WizardResult(True, ["SSH port range (default 22):"], "Input>")
        if step == WizardStep.SSH_BRUTE:
            return WizardResult(True, ["Brute-force SSH with hydra? [y/n]:"], "Select>")
        if step == WizardStep.WIN_WINRM:
            return WizardResult(True, ["Connect with Evil-WinRM? [y/n]:"], "Select>")
        if step == WizardStep.PREVIEW:
            self._awaiting_confirm = True
            chain = self.state.command_chain
            target = self.state.choices.get("target", "")
            flags = chain.split(" ")[1:] if chain else []
            impact = generate_impact_description(flags, target) if target else "N/A"
            box = format_confirmation_box(chain, target, impact)
            return WizardResult(True, [box], "Confirm>")
        if step == WizardStep.TOOL_SELECT:
            return self._tool_menu_result()
        return self._menu_result()

    def _tool_menu_result(self) -> WizardResult:
        return WizardResult(
            True,
            [self.TOOL_MENU.format(warning=AUTHORIZED_SCOPE_WARNING)],
            "Select>",
        )

    def _menu_result(self) -> WizardResult:
        return WizardResult(
            True,
            [self.ATTACK_MENU.format(warning=AUTHORIZED_SCOPE_WARNING)],
            "Select>",
        )

    def _target_prompt(self) -> str:
        return (
            "Enter target (IP, CIDR, hostname, or range):\n"
            "Examples: 192.168.1.1 | 192.168.1.0/24 | target.local"
        )

    def _current_prompt(self) -> str:
        prompts = {
            WizardStep.TOOL_SELECT: "Select>",
            WizardStep.ATTACK_MENU: "Select>",
            WizardStep.TARGET: "Input>",
            WizardStep.SCAN_LEVEL: "Level>",
            WizardStep.SUGGESTION: "Wizard>",
            WizardStep.SUGGESTION_EDIT: "Input>",
            WizardStep.WEB_DIR_SCAN: "Select>",
            WizardStep.WEB_DIR_TOOL: "Select>",
            WizardStep.WEB_URL: "Input>",
            WizardStep.WEB_WORDLIST: "Input>",
            WizardStep.SSH_PORT_RANGE: "Input>",
            WizardStep.SSH_BRUTE: "Select>",
            WizardStep.SSH_USERLIST: "Input>",
            WizardStep.SSH_PASSLIST: "Input>",
            WizardStep.WIN_WINRM: "Select>",
            WizardStep.WIN_USERNAME: "Input>",
            WizardStep.WIN_PASSWORD: "Password>",
            WizardStep.DB_TYPE: "Select>",
            WizardStep.CUSTOM_FLAGS: "Input>",
            WizardStep.PREVIEW: "Confirm>",
        }
        return prompts.get(self.state.current_step, "Select>")

    def _help_text(self) -> str:
        return """
WIZARD HELP
-----------
Global commands: check | install | back | reset | help | cancel

Step 1: Select a tool. DEMO VERSION supports Nmap only —
        Masscan/Hydra/Ncrack/Evil-WinRM/Auto Chain are blocked at this step.

Step 2 (after target): Select a scan intensity level:
  -- Stealth --
   1. Stealth SYN scan
   2. Fragmented stealth
  -- Verbose / Info Gathering --
   3. Verbose service scan
   4. Verbose + script scan
  -- Aggressive / Critical (ใช้ด้วยความระมัดระวัง) --
   5. Aggressive full detect
   6. Brute-timing critical
   7. Vulnerability script scan

Attack paths (Nmap only in this demo):
 1 Web Servers     nmap http scripts
 2 SSH Services    nmap port scan
 3 Windows Systems nmap SMB/WinRM ports
 4 Databases       nmap DB scripts on common ports
 5 Full Network    nmap -sV -O on target range
 6 Custom Scan     user-defined nmap flags (validated)

Chaining to gobuster/dirb/hydra/evil-winrm is disabled in this demo.
Every command requires typing the literal word "yes" at the
COMMAND PREVIEW confirmation gate before it executes. Every
confirmation (yes or no) is written to the audit log.

Cancel via Ctrl+C during execution, or type "cancel" + Enter.
"""

    def _tool_available(self, name: str) -> bool:
        return shutil.which(name) is not None

    def get_command_chain(self) -> str:
        return self.state.command_chain

    def execution_finished(self) -> WizardResult:
        self._awaiting_confirm = False
        self.state.current_cancel_command = ""
        self.state.reset_flow()
        lines = [
            "",
            "[+] Command chain finished.",
            "[*] Type reset to start a new wizard session.",
            "",
            self.ATTACK_MENU.format(warning=AUTHORIZED_SCOPE_WARNING),
        ]
        return WizardResult(True, lines, "Select>")

    def handle_cancelled(self) -> WizardResult:
        """Handle Ctrl+C or cancel during execution. Resets state and logs to audit."""
        chain = self.state.current_cancel_command or self.state.command_chain
        target = self.state.choices.get("target", "")
        # Log the cancellation
        from src.core.wizard_safety import audit_log_cancel
        audit_log_cancel(command=chain, target=target, reason="ctrl_c_or_cancel_command")
        self._awaiting_confirm = False
        self.state.current_cancel_command = ""
        self.state.reset_flow()
        lines = [
            "",
            "[!] Process ถูกยกเลิกโดยผู้ใช้",
            "[*] Type reset to start a new wizard session.",
            "",
            self.ATTACK_MENU.format(warning=AUTHORIZED_SCOPE_WARNING),
        ]
        return WizardResult(True, lines, "Select>")


_wizard_engine_instance: Optional[WizardEngine] = None


def get_wizard_engine() -> WizardEngine:
    global _wizard_engine_instance
    if _wizard_engine_instance is None:
        _wizard_engine_instance = WizardEngine()
    return _wizard_engine_instance