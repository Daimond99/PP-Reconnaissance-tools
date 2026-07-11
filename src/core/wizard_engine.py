"""
Recon Tool - Wizard Engine Module
ระบบ Wizard แบบ interactive คล้าย Hydra wizard mode
นำผู้ใช้ผ่าน attack chain step-by-step
"""

import platform
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class WizardStep(Enum):
    """ขั้นตอนต่างๆ ใน wizard"""
    TARGET_INPUT = "target_input"
    SCAN_TYPE = "scan_type"
    TOOL_SELECTION = "tool_selection"
    OPTIONS_CONFIG = "options_config"
    CREDENTIAL_CONFIG = "credential_config"
    OUTPUT_CONFIG = "output_config"
    PREVIEW = "preview"
    EXECUTE = "execute"


class AttackType(Enum):
    """ประเภทของการโจมตี"""
    WEB_SERVERS = "web_servers"
    SSH_SERVICES = "ssh_services"
    WINDOWS_SYSTEMS = "windows_systems"
    DATABASES = "databases"
    FULL_NETWORK = "full_network"
    CUSTOM_SCAN = "custom_scan"


@dataclass
class WizardState:
    """เก็บสถานะปัจจุบันของ wizard"""
    current_step: WizardStep = WizardStep.TARGET_INPUT
    attack_type: Optional[AttackType] = None
    target: str = ""
    target_type: str = "CIDR"
    selected_tool: str = ""
    tool_options: Dict[str, Any] = field(default_factory=dict)
    credentials: Dict[str, str] = field(default_factory=dict)
    output_format: str = "normal"
    output_file: str = ""
    command: str = ""
    
    # History สำหรับ back navigation
    step_history: List[WizardStep] = field(default_factory=list)
    
    def go_back(self) -> bool:
        """ย้อนกลับไป step ก่อนหน้า"""
        if self.step_history:
            self.current_step = self.step_history.pop()
            return True
        return False
    
    def advance_to(self, step: WizardStep):
        """ไปยัง step ถัดไป"""
        self.step_history.append(self.current_step)
        self.current_step = step


@dataclass
class WizardOption:
    """ตัวเลือกใน wizard prompt"""
    key: str
    label: str
    description: str
    value: Any = None
    is_default: bool = False


@dataclass
class WizardPrompt:
    """Prompt สำหรับ wizard step"""
    title: str
    message: str
    options: List[WizardOption] = field(default_factory=list)
    input_type: str = "choice"  # choice, text, password, file
    default_value: str = ""
    allow_back: bool = True
    allow_custom: bool = False


class WizardEngine:
    """Engine หลักสำหรับ wizard mode"""
    
    def __init__(self):
        self.state = WizardState()
        self.is_windows = platform.system() == "Windows"
        self._setup_attack_chains()
    
    def _setup_attack_chains(self):
        """กำหนด attack chains สำหรับแต่ละประเภท"""
        
        # Attack chain definitions
        # แต่ละ attack type จะมี sequence ของ steps ที่ต้องผ่าน
        self.attack_chains = {
            AttackType.WEB_SERVERS: [
                WizardStep.TARGET_INPUT,
                WizardStep.SCAN_TYPE,
                WizardStep.OPTIONS_CONFIG,
                WizardStep.OUTPUT_CONFIG,
                WizardStep.PREVIEW,
                WizardStep.EXECUTE
            ],
            AttackType.SSH_SERVICES: [
                WizardStep.TARGET_INPUT,
                WizardStep.SCAN_TYPE,
                WizardStep.CREDENTIAL_CONFIG,
                WizardStep.OUTPUT_CONFIG,
                WizardStep.PREVIEW,
                WizardStep.EXECUTE
            ],
            AttackType.WINDOWS_SYSTEMS: [
                WizardStep.TARGET_INPUT,
                WizardStep.SCAN_TYPE,
                WizardStep.TOOL_SELECTION,
                WizardStep.CREDENTIAL_CONFIG,
                WizardStep.OUTPUT_CONFIG,
                WizardStep.PREVIEW,
                WizardStep.EXECUTE
            ],
            AttackType.DATABASES: [
                WizardStep.TARGET_INPUT,
                WizardStep.SCAN_TYPE,
                WizardStep.OPTIONS_CONFIG,
                WizardStep.OUTPUT_CONFIG,
                WizardStep.PREVIEW,
                WizardStep.EXECUTE
            ],
            AttackType.FULL_NETWORK: [
                WizardStep.TARGET_INPUT,
                WizardStep.SCAN_TYPE,
                WizardStep.OUTPUT_CONFIG,
                WizardStep.PREVIEW,
                WizardStep.EXECUTE
            ],
            AttackType.CUSTOM_SCAN: [
                WizardStep.TARGET_INPUT,
                WizardStep.TOOL_SELECTION,
                WizardStep.OPTIONS_CONFIG,
                WizardStep.OUTPUT_CONFIG,
                WizardStep.PREVIEW,
                WizardStep.EXECUTE
            ]
        }
    
    def reset(self):
        """รีเซ็ต wizard state"""
        self.state = WizardState()
    
    def get_current_prompt(self) -> WizardPrompt:
        """ดึง prompt สำหรับ step ปัจจุบัน"""
        
        if self.state.current_step == WizardStep.TARGET_INPUT:
            return self._prompt_target_input()
        
        elif self.state.current_step == WizardStep.SCAN_TYPE:
            return self._prompt_scan_type()
        
        elif self.state.current_step == WizardStep.TOOL_SELECTION:
            return self._prompt_tool_selection()
        
        elif self.state.current_step == WizardStep.OPTIONS_CONFIG:
            return self._prompt_options_config()
        
        elif self.state.current_step == WizardStep.CREDENTIAL_CONFIG:
            return self._prompt_credential_config()
        
        elif self.state.current_step == WizardStep.OUTPUT_CONFIG:
            return self._prompt_output_config()
        
        elif self.state.current_step == WizardStep.PREVIEW:
            return self._prompt_preview()
        
        elif self.state.current_step == WizardStep.EXECUTE:
            return self._prompt_execute()
        
        return WizardPrompt(title="Unknown", message="Unknown step")
    
    def _prompt_target_input(self) -> WizardPrompt:
        """Prompt สำหรับกรอก target"""
        return WizardPrompt(
            title="TARGET INPUT",
            message="What is your target?\n\nExamples:\n  - Single IP: 192.168.1.1\n  - CIDR Range: 192.168.1.0/24\n  - Multiple: 192.168.1.1-100\n  - Hostname: target.example.com",
            input_type="text",
            default_value="192.168.1.0/24",
            allow_back=False
        )
    
    def _prompt_scan_type(self) -> WizardPrompt:
        """Prompt สำหรับเลือก scan type"""
        options = [
            WizardOption("1", "Quick Scan", "Fast scan of common ports (top 100)", is_default=True),
            WizardOption("2", "Full Port Scan", "Scan all 65535 ports"),
            WizardOption("3", "Service Detection", "Detect service versions"),
            WizardOption("4", "Stealth Scan", "SYN stealth scan (requires root/admin)"),
            WizardOption("5", "Aggressive Scan", "Enable OS detection, version detection, script scanning"),
            WizardOption("6", "Vulnerability Scan", "Run vulnerability scripts"),
        ]
        
        if self.state.attack_type == AttackType.SSH_SERVICES:
            options.append(WizardOption("7", "SSH Brute Force", "Attempt to brute force SSH"))
        
        elif self.state.attack_type == AttackType.WINDOWS_SYSTEMS:
            options.append(WizardOption("7", "WinRM Attack", "Attack via WinRM service"))
            options.append(WizardOption("8", "SMB Enumeration", "Enumerate SMB shares and users"))
        
        return WizardPrompt(
            title="SCAN TYPE",
            message="Select scan type:",
            options=options,
            input_type="choice",
            allow_back=True
        )
    
    def _prompt_tool_selection(self) -> WizardPrompt:
        """Prompt สำหรับเลือก tool"""
        options = []
        
        # Network Scanners
        options.append(WizardOption("1", "Nmap", "Full-featured network scanner", is_default=True))
        options.append(WizardOption("2", "Masscan", "Fast asynchronous port scanner"))
        
        # Connection Tools
        options.append(WizardOption("3", "Ncat", "Network connectivity tool"))
        
        # Password Attack Tools
        if self.state.attack_type in [AttackType.SSH_SERVICES, AttackType.WINDOWS_SYSTEMS]:
            options.append(WizardOption("4", "Hydra", "Fast network logon cracker"))
            options.append(WizardOption("5", "Ncrack", "Network authentication cracker"))
        
        # Windows Attack Tools
        if self.state.attack_type == AttackType.WINDOWS_SYSTEMS:
            options.append(WizardOption("6", "Evil-WinRM", "WinRM shell for hacking"))
        
        return WizardPrompt(
            title="TOOL SELECTION",
            message="Select tool to use:",
            options=options,
            input_type="choice",
            allow_back=True
        )
    
    def _prompt_options_config(self) -> WizardPrompt:
        """Prompt สำหรับ configure options"""
        tool = self.state.selected_tool.lower()
        options = []
        
        if tool == "nmap":
            options = [
                WizardOption("1", "Default Options", "Use recommended default options", is_default=True),
                WizardOption("2", "Custom Ports", "Specify ports to scan"),
                WizardOption("3", "Timing Template", "Set timing template (T0-T5)"),
                WizardOption("4", "Script Selection", "Choose NSE scripts to run"),
                WizardOption("5", "Advanced Options", "Set advanced flags"),
            ]
        
        elif tool == "masscan":
            options = [
                WizardOption("1", "Default Rate (10000 pps)", "Recommended for most networks", is_default=True),
                WizardOption("2", "Slow Rate (1000 pps)", "For sensitive networks"),
                WizardOption("3", "Fast Rate (100000 pps)", "For fast networks only"),
                WizardOption("4", "Custom Rate", "Specify packets per second"),
            ]
        
        elif tool == "hydra":
            options = [
                WizardOption("1", "Use Wordlist", "Specify username/password wordlists"),
                WizardOption("2", "Single User", "Try single username with wordlist"),
                WizardOption("3", "Single Password", "Try single password with userlist"),
                WizardOption("4", "Custom Options", "Set advanced Hydra options"),
            ]
        
        elif tool == "ncrack":
            options = [
                WizardOption("1", "Default Options", "Use recommended defaults", is_default=True),
                WizardOption("2", "Custom Wordlists", "Specify user/pass wordlists"),
                WizardOption("3", "Timing Options", "Set timing and threads"),
            ]
        
        elif tool == "evil-winrm":
            options = [
                WizardOption("1", "Password Authentication", "Login with password"),
                WizardOption("2", "Hash Authentication", "Login with NTLM hash"),
                WizardOption("3", "Certificate", "Login with certificate"),
                WizardOption("4", "SSL Options", "Configure SSL settings"),
            ]
        
        else:
            options = [WizardOption("1", "Default Options", "Use default settings", is_default=True)]
        
        return WizardPrompt(
            title="OPTIONS CONFIGURATION",
            message="Configure tool options:",
            options=options,
            input_type="choice",
            allow_back=True
        )
    
    def _prompt_credential_config(self) -> WizardPrompt:
        """Prompt สำหรับ configure credentials"""
        tool = self.state.selected_tool.lower()
        options = []
        
        if tool in ["hydra", "ncrack"]:
            return WizardPrompt(
                title="CREDENTIAL CONFIGURATION",
                message="Configure authentication testing:\n\nYou can use:\n  - Username: single username or wordlist file\n  - Password: single password or wordlist file\n  - Common wordlists:\n    - /usr/share/wordlists/rockyou.txt (Linux)\n    - C:\\tools\\wordlists\\rockyou.txt (Windows)",
                options=[
                    WizardOption("1", "Use Default Wordlists", "Use rockyou.txt wordlist"),
                    WizardOption("2", "Custom Wordlists", "Specify custom wordlist paths"),
                    WizardOption("3", "Single User/Pass", "Test single username/password"),
                ],
                input_type="choice",
                allow_back=True
            )
        
        elif tool == "evil-winrm":
            return WizardPrompt(
                title="CREDENTIAL CONFIGURATION",
                message="Enter credentials for WinRM connection:",
                options=[
                    WizardOption("1", "Username", "Enter username", value=self.state.credentials.get("username", "")),
                    WizardOption("2", "Password", "Enter password", value=self.state.credentials.get("password", "")),
                    WizardOption("3", "Domain", "Enter domain (optional)", value=self.state.credentials.get("domain", "")),
                ],
                input_type="choice",
                allow_back=True
            )
        
        return WizardPrompt(
            title="CREDENTIAL CONFIGURATION",
            message="No credentials needed for this tool.",
            options=[WizardOption("1", "Continue", "Proceed without credentials", is_default=True)],
            input_type="choice",
            allow_back=True
        )
    
    def _prompt_output_config(self) -> WizardPrompt:
        """Prompt สำหรับ configure output"""
        return WizardPrompt(
            title="OUTPUT CONFIGURATION",
            message="Configure output options:",
            options=[
                WizardOption("1", "Normal Output", "Display to screen only", is_default=True),
                WizardOption("2", "Save to File", "Save results to file"),
                WizardOption("3", "XML Format", "Export in XML format"),
                WizardOption("4", "JSON Format", "Export in JSON format (if supported)"),
                WizardOption("5", "All Formats", "Save in all available formats"),
            ],
            input_type="choice",
            allow_back=True
        )
    
    def _prompt_preview(self) -> WizardPrompt:
        """Prompt สำหรับ preview command"""
        command = self._build_command()
        self.state.command = command
        
        return WizardPrompt(
            title="COMMAND PREVIEW",
            message=f"Generated command:\n\n{command}\n\nReady to execute?",
            options=[
                WizardOption("1", "Execute", "Run this command now", is_default=True),
                WizardOption("2", "Edit Command", "Modify the command manually"),
                WizardOption("3", "Back", "Go back and change options"),
                WizardOption("4", "Cancel", "Abort this wizard"),
            ],
            input_type="choice",
            allow_back=True
        )
    
    def _prompt_execute(self) -> WizardPrompt:
        """Prompt สำหรับ execute"""
        return WizardPrompt(
            title="EXECUTING",
            message=f"Executing command:\n\n{self.state.command}\n\nPress Ctrl+C to stop...",
            options=[],
            input_type="none",
            allow_back=False
        )
    
    def process_input(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล input จากผู้ใช้
        
        Returns:
            tuple: (success, message)
        """
        step = self.state.current_step
        
        try:
            if step == WizardStep.TARGET_INPUT:
                return self._process_target_input(user_input)
            elif step == WizardStep.SCAN_TYPE:
                return self._process_scan_type(user_input)
            elif step == WizardStep.TOOL_SELECTION:
                return self._process_tool_selection(user_input)
            elif step == WizardStep.OPTIONS_CONFIG:
                return self._process_options_config(user_input)
            elif step == WizardStep.CREDENTIAL_CONFIG:
                return self._process_credential_config(user_input)
            elif step == WizardStep.OUTPUT_CONFIG:
                return self._process_output_config(user_input)
            elif step == WizardStep.PREVIEW:
                return self._process_preview(user_input)
            else:
                return False, "Unknown step"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def _process_target_input(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล target input"""
        target = user_input.strip()
        if not target:
            return False, "Target cannot be empty"
        
        self.state.target = target
        self._detect_target_type(target)
        self._advance_step()
        return True, f"Target set to: {target}"
    
    def _process_scan_type(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล scan type selection"""
        choice = user_input.strip()
        
        scan_type_map = {
            "1": "quick",
            "2": "full",
            "3": "service",
            "4": "stealth",
            "5": "aggressive",
            "6": "vuln",
            "7": "brute" if self.state.attack_type == AttackType.SSH_SERVICES else "winrm",
            "8": "smb"
        }
        
        if choice not in scan_type_map:
            return False, f"Invalid choice: {choice}"
        
        self.state.tool_options["scan_type"] = scan_type_map[choice]
        
        # Set tool based on scan type
        if scan_type_map[choice] == "brute":
            self.state.selected_tool = "hydra"
        elif scan_type_map[choice] == "winrm":
            self.state.selected_tool = "evil-winrm"
        else:
            self.state.selected_tool = "nmap"
        
        self._advance_step()
        return True, f"Scan type: {scan_type_map[choice]}"
    
    def _process_tool_selection(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล tool selection"""
        choice = user_input.strip()
        
        tool_map = {
            "1": "nmap",
            "2": "masscan",
            "3": "ncat",
            "4": "hydra",
            "5": "ncrack",
            "6": "evil-winrm"
        }
        
        if choice not in tool_map:
            return False, f"Invalid choice: {choice}"
        
        self.state.selected_tool = tool_map[choice]
        self._advance_step()
        return True, f"Selected tool: {tool_map[choice]}"
    
    def _process_options_config(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล options config"""
        choice = user_input.strip()
        
        tool = self.state.selected_tool.lower()
        
        if tool == "nmap":
            options_map = {
                "1": {"timing": "4"},
                "2": {"custom_ports": True},
                "3": {"timing": "custom"},
                "4": {"scripts": True},
                "5": {"advanced": True}
            }
        elif tool == "masscan":
            rate_map = {"1": "10000", "2": "1000", "3": "100000", "4": "custom"}
            self.state.tool_options["rate"] = rate_map.get(choice, "10000")
            self._advance_step()
            return True, f"Rate set to: {self.state.tool_options['rate']} pps"
        else:
            options_map = {"1": {"default": True}}
        
        if choice in options_map:
            self.state.tool_options.update(options_map[choice])
            self._advance_step()
            return True, "Options configured"
        
        return False, f"Invalid choice: {choice}"
    
    def _process_credential_config(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล credential config"""
        # For now, use default wordlists
        choice = user_input.strip()
        
        tool = self.state.selected_tool.lower()
        
        if tool in ["hydra", "ncrack"]:
            if choice == "1":
                if self.is_windows:
                    self.state.credentials["userlist"] = "C:\\tools\\wordlists\\users.txt"
                    self.state.credentials["passlist"] = "C:\\tools\\wordlists\\rockyou.txt"
                else:
                    self.state.credentials["userlist"] = "/usr/share/wordlists/metasploit/unix_users.txt"
                    self.state.credentials["passlist"] = "/usr/share/wordlists/rockyou.txt"
            # choice 2 and 3 would require additional input prompts
        
        self._advance_step()
        return True, "Credentials configured"
    
    def _process_output_config(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล output config"""
        choice = user_input.strip()
        
        output_map = {
            "1": "normal",
            "2": "file",
            "3": "xml",
            "4": "json",
            "5": "all"
        }
        
        if choice not in output_map:
            return False, f"Invalid choice: {choice}"
        
        self.state.output_format = output_map[choice]
        self._advance_step()
        return True, f"Output format: {output_map[choice]}"
    
    def _process_preview(self, user_input: str) -> tuple[bool, str]:
        """ประมวลผล preview action"""
        choice = user_input.strip()
        
        if choice == "1":  # Execute
            self.state.advance_to(WizardStep.EXECUTE)
            return True, "EXECUTE"
        elif choice == "2":  # Edit
            return True, "EDIT"
        elif choice == "3":  # Back
            self.state.go_back()
            return True, "BACK"
        elif choice == "4":  # Cancel
            self.reset()
            return True, "CANCEL"
        
        return False, f"Invalid choice: {choice}"
    
    def _detect_target_type(self, target: str):
        """ตรวจจับประเภทของ target"""
        if "/" in target:
            self.state.target_type = "CIDR"
        elif "-" in target:
            self.state.target_type = "Range"
        elif target.replace(".", "").isdigit():
            self.state.target_type = "IP"
        else:
            self.state.target_type = "Hostname"
    
    def _advance_step(self):
        """ไปยัง step ถัดไปตาม attack chain"""
        attack_type = self.state.attack_type
        if attack_type not in self.attack_chains:
            return
        
        chain = self.attack_chains[attack_type]
        current_index = -1
        
        for i, step in enumerate(chain):
            if step == self.state.current_step:
                current_index = i
                break
        
        if current_index >= 0 and current_index < len(chain) - 1:
            next_step = chain[current_index + 1]
            self.state.advance_to(next_step)
    
    def set_attack_type(self, attack_type: AttackType):
        """ตั้งค่า attack type"""
        self.state.attack_type = attack_type
        # Reset to first step of the chain
        if attack_type in self.attack_chains:
            first_step = self.attack_chains[attack_type][0]
            self.state.current_step = first_step
            self.state.step_history = []
    
    def go_back(self) -> bool:
        """ย้อนกลับไป step ก่อนหน้า"""
        return self.state.go_back()
    
    def _build_command(self) -> str:
        """สร้าง command จาก current state"""
        tool = self.state.selected_tool.lower()
        target = self.state.target
        options = self.state.tool_options
        credentials = self.state.credentials
        output_format = self.state.output_format
        
        if tool == "nmap":
            return self._build_nmap_command(target, options, output_format)
        elif tool == "masscan":
            return self._build_masscan_command(target, options, output_format)
        elif tool == "hydra":
            return self._build_hydra_command(target, credentials, output_format)
        elif tool == "ncrack":
            return self._build_ncrack_command(target, credentials, output_format)
        elif tool == "evil-winrm":
            return self._build_evilwinrm_command(target, credentials)
        elif tool == "ncat":
            return self._build_ncat_command(target, options)
        
        return f"echo 'Unknown tool: {tool}'"
    
    def _build_nmap_command(self, target: str, options: dict, output: str) -> str:
        """สร้าง nmap command"""
        cmd_parts = ["nmap"]
        
        scan_type = options.get("scan_type", "quick")
        
        # Scan type options
        if scan_type == "quick":
            cmd_parts.extend(["-F"])  # Fast scan
        elif scan_type == "full":
            cmd_parts.extend(["-p-"])  # All ports
        elif scan_type == "service":
            cmd_parts.extend(["-sV", "-p-"])
        elif scan_type == "stealth":
            cmd_parts.extend(["-sS", "-p-"])
        elif scan_type == "aggressive":
            cmd_parts.extend(["-A", "-T4"])
        elif scan_type == "vuln":
            cmd_parts.extend(["--script", "vuln", "-sV"])
        
        # Timing
        timing = options.get("timing", "4")
        if timing != "custom":
            cmd_parts.append(f"-T{timing}")
        
        # Output options
        if output == "xml" or output == "all":
            cmd_parts.extend(["-oX", f"scan_{target.replace('/', '_')}.xml"])
        elif output == "json":
            # Nmap doesn't have native JSON, but we can try
            pass
        
        cmd_parts.append(target)
        
        return " ".join(cmd_parts)
    
    def _build_masscan_command(self, target: str, options: dict, output: str) -> str:
        """สร้าง masscan command"""
        cmd_parts = ["masscan"]
        
        # Ports
        cmd_parts.extend(["-p", "1-65535"])
        
        # Rate
        rate = options.get("rate", "10000")
        cmd_parts.extend(["--rate", rate])
        
        # Output
        if output != "normal":
            cmd_parts.extend(["-oL", f"masscan_{target.replace('/', '_')}.txt"])
        
        cmd_parts.append(target)
        
        return " ".join(cmd_parts)
    
    def _build_hydra_command(self, target: str, credentials: dict, output: str) -> str:
        """สร้าง hydra command (wizard style)"""
        cmd_parts = ["hydra"]
        
        userlist = credentials.get("userlist", "")
        passlist = credentials.get("passlist", "")
        
        if userlist:
            cmd_parts.extend(["-L", userlist])
        else:
            cmd_parts.extend(["-l", "admin"])
        
        if passlist:
            cmd_parts.extend(["-P", passlist])
        else:
            cmd_parts.extend(["-p", "password"])
        
        # Service
        cmd_parts.append("ssh")
        
        # Target
        cmd_parts.append(target)
        
        # Output
        if output != "normal":
            cmd_parts.extend(["-o", f"hydra_{target.replace('/', '_')}.txt"])
        
        return " ".join(cmd_parts)
    
    def _build_ncrack_command(self, target: str, credentials: dict, output: str) -> str:
        """สร้าง ncrack command"""
        cmd_parts = ["ncrack"]
        
        userlist = credentials.get("userlist", "")
        passlist = credentials.get("passlist", "")
        
        if userlist:
            cmd_parts.extend(["-U", userlist])
        else:
            cmd_parts.extend(["-u", "admin"])
        
        if passlist:
            cmd_parts.extend(["-P", passlist])
        else:
            cmd_parts.extend(["-p", "password"])
        
        # Service and target
        cmd_parts.append(f"ssh://{target}")
        
        return " ".join(cmd_parts)
    
    def _build_evilwinrm_command(self, target: str, credentials: dict) -> str:
        """สร้าง evil-winrm command"""
        cmd_parts = ["evil-winrm"]
        
        cmd_parts.extend(["-i", target])
        
        username = credentials.get("username", "Administrator")
        password = credentials.get("password", "")
        
        cmd_parts.extend(["-u", username])
        
        if password:
            cmd_parts.extend(["-p", password])
        
        return " ".join(cmd_parts)
    
    def _build_ncat_command(self, target: str, options: dict) -> str:
        """สร้าง ncat command"""
        cmd_parts = ["ncat"]
        
        # Verbose
        cmd_parts.append("-v")
        
        # Target and port
        cmd_parts.extend([target, "80"])
        
        return " ".join(cmd_parts)
    
    def get_command(self) -> str:
        """ดึง command ที่สร้างแล้ว"""
        if not self.state.command:
            self.state.command = self._build_command()
        return self.state.command


# สร้าง instance เดียวสำหรับใช้ทั้งโปรแกรม
_wizard_engine_instance = None

def get_wizard_engine() -> WizardEngine:
    """ดึง WizardEngine instance"""
    global _wizard_engine_instance
    if _wizard_engine_instance is None:
        _wizard_engine_instance = WizardEngine()
    return _wizard_engine_instance
