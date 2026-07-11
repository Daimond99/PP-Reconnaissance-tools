"""
Recon Tool - Tool Manager Module
จัดการการตรวจสอบและติดตั้ง tools ต่างๆ
รองรับทั้ง Windows และ Linux
"""

import subprocess
import platform
import shutil
import threading
from typing import Dict, List, Optional, Tuple


class ToolInfo:
    """เก็บข้อมูลของแต่ละ tool"""
    
    def __init__(self, name: str, display_name: str, description: str,
                 windows_cmd: str, linux_cmd: str,
                 install_windows: str, install_linux: str,
                 category: str):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.windows_cmd = windows_cmd
        self.linux_cmd = linux_cmd
        self.install_windows = install_windows
        self.install_linux = install_linux
        self.category = category
        self.is_installed = False
        self.version = None


class ToolManager:
    """จัดการการตรวจสอบและติดตั้ง security tools"""
    
    def __init__(self):
        self.is_windows = platform.system() == "Windows"
        self.tools: Dict[str, ToolInfo] = {}
        self._checked = False
        self._check_lock = threading.Lock()
        self._initialize_tools()
        self._schedule_tool_check()
    
    def _schedule_tool_check(self):
        """ตรวจสอบ tools ใน background เพื่อไม่ block UI startup"""
        threading.Thread(target=self._check_all_tools, daemon=True).start()
    
    def _ensure_checked(self):
        """รอให้การตรวจสอบครั้งแรกเสร็จก่อนอ่านสถานะ"""
        if not self._checked:
            self._check_all_tools()
    
    def _initialize_tools(self):
        """กำหนดข้อมูลของ tools ทั้งหมด"""
        
        # Network Scanners
        self.tools["nmap"] = ToolInfo(
            name="nmap",
            display_name="Nmap",
            description="Network discovery and security auditing",
            windows_cmd="nmap",
            linux_cmd="nmap",
            install_windows="Download from https://nmap.org/download.html\nOr use: choco install nmap",
            install_linux="sudo apt install nmap  # Debian/Ubuntu\nsudo yum install nmap  # RHEL/CentOS\nsudo pacman -S nmap  # Arch Linux",
            category="Network Scanner"
        )
        
        self.tools["masscan"] = ToolInfo(
            name="masscan",
            display_name="Masscan",
            description="Fast TCP port scanner",
            windows_cmd="masscan",
            linux_cmd="masscan",
            install_windows="Download from https://github.com/robertdavidgraham/masscan/releases\nOr compile from source on Windows",
            install_linux="sudo apt install masscan  # Debian/Ubuntu\nsudo yum install masscan  # RHEL/CentOS\nOr compile: git clone https://github.com/robertdavidgraham/masscan",
            category="Network Scanner"
        )
        
        # Connection Tools
        self.tools["ncat"] = ToolInfo(
            name="ncat",
            display_name="Ncat",
            description="Network connectivity tool (part of Nmap suite)",
            windows_cmd="ncat",
            linux_cmd="ncat",
            install_windows="Installed with Nmap\nOr: choco install nmap",
            install_linux="sudo apt install nmap  # Debian/Ubuntu\nsudo yum install nmap  # RHEL/CentOS\nOr: sudo apt install netcat",
            category="Connection Tool"
        )
        
        # Password Attack Tools
        self.tools["hydra"] = ToolInfo(
            name="hydra",
            display_name="Hydra",
            description="Fast network logon cracker",
            windows_cmd="hydra",
            linux_cmd="hydra",
            install_windows="Download from https://github.com/maaaaz/thc-hydra-windows\nOr use Kali Linux WSL",
            install_linux="sudo apt install hydra  # Debian/Ubuntu\nsudo yum install hydra  # RHEL/CentOS\nOr compile: git clone https://github.com/vanhauser-thc/thc-hydra",
            category="Password Attack"
        )
        
        self.tools["ncrack"] = ToolInfo(
            name="ncrack",
            display_name="Ncrack",
            description="Network authentication cracker",
            windows_cmd="ncrack",
            linux_cmd="ncrack",
            install_windows="Download from https://nmap.org/ncrack/\nOr: choco install ncrack",
            install_linux="sudo apt install ncrack  # Debian/Ubuntu\nOr compile: git clone https://github.com/nmap/ncrack",
            category="Password Attack"
        )
        
        # Windows Attack Tools
        self.tools["evil-winrm"] = ToolInfo(
            name="evil-winrm",
            display_name="Evil-WinRM",
            description="WinRM shell for hacking",
            windows_cmd="evil-winrm",
            linux_cmd="evil-winrm",
            install_windows="gem install evil-winrm\n(Requires Ruby and DevKit)\nOr use WSL: sudo gem install evil-winrm",
            install_linux="sudo gem install evil-winrm\nOr: sudo apt install evil-winrm  # Kali Linux",
            category="Windows Attack"
        )
    
    def _check_tool_installed(self, tool_name: str) -> Tuple[bool, Optional[str]]:
        """ตรวจสอบว่า tool ติดตั้งแล้วหรือไม่ และดึง version"""
        tool = self.tools.get(tool_name)
        if not tool:
            return False, None
        
        cmd = tool.windows_cmd if self.is_windows else tool.linux_cmd

        if shutil.which(cmd) is None:
            return False, None
        
        # ลองดึง version
        version = None
        version_flags = {
            "nmap": ["--version"],
            "masscan": ["--version"],
            "ncat": ["--version"],
            "hydra": ["-h"],
            "ncrack": ["--version"],
            "evil-winrm": ["--version"]
        }
        
        if tool_name in version_flags:
            try:
                version_cmd = [cmd] + version_flags[tool_name]
                result = subprocess.run(
                    version_cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0,
                    timeout=5
                )
                if result.returncode == 0 or result.stdout:
                    # ดึงบรรทัดแรกของ output
                    lines = (result.stdout or result.stderr).strip().split('\n')
                    if lines:
                        version = lines[0][:100]  # จำกัดความยาว
            except Exception:
                pass
        
        return True, version
    
    def _check_all_tools(self):
        """ตรวจสอบการติดตั้งของทุก tools"""
        with self._check_lock:
            if self._checked:
                return
            for tool_name in self.tools:
                installed, version = self._check_tool_installed(tool_name)
                self.tools[tool_name].is_installed = installed
                self.tools[tool_name].version = version
            self._checked = True
    
    def get_tool_status(self, tool_name: str) -> Tuple[bool, str]:
        """ดึงสถานะของ tool"""
        self._ensure_checked()
        tool = self.tools.get(tool_name)
        if not tool:
            return False, f"Unknown tool: {tool_name}"
        
        if tool.is_installed:
            status = f"✓ {tool.display_name} - Installed"
            if tool.version:
                status += f"\n  {tool.version}"
            return True, status
        else:
            status = f"✗ {tool.display_name} - NOT INSTALLED"
            if self.is_windows:
                status += f"\n  Install: {tool.install_windows}"
            else:
                status += f"\n  Install: {tool.install_linux}"
            return False, status
    
    def get_all_status(self) -> Dict[str, Tuple[bool, str]]:
        """ดึงสถานะของทุก tools"""
        return {name: self.get_tool_status(name) for name in self.tools}
    
    def get_installed_tools(self) -> List[str]:
        """ดึงรายชื่อ tools ที่ติดตั้งแล้ว"""
        self._ensure_checked()
        return [name for name, tool in self.tools.items() if tool.is_installed]
    
    def get_missing_tools(self) -> List[str]:
        """ดืงรายชื่อ tools ที่ยังไม่ติดตั้ง"""
        self._ensure_checked()
        return [name for name, tool in self.tools.items() if not tool.is_installed]
    
    def get_tools_by_category(self) -> Dict[str, List[str]]:
        """จัดกลุ่ม tools ตามหมวดหมู่"""
        categories = {}
        for name, tool in self.tools.items():
            if tool.category not in categories:
                categories[tool.category] = []
            categories[tool.category].append(name)
        return categories
    
    def get_install_guide(self, tool_name: str) -> str:
        """ดึงคำแนะนำการติดตั้ง"""
        tool = self.tools.get(tool_name)
        if not tool:
            return "Unknown tool"
        
        if self.is_windows:
            return tool.install_windows
        else:
            return tool.install_linux
    
    def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """ดึงข้อมูลของ tool"""
        return self.tools.get(tool_name)
    
    def refresh(self):
        """รีเฟรชการตรวจสอบ tools"""
        with self._check_lock:
            self._checked = False
        self._check_all_tools()


# สร้าง instance เดียวสำหรับใช้ทั้งโปรแกรม
_tool_manager_instance = None

def get_tool_manager() -> ToolManager:
    """ดึง ToolManager instance"""
    global _tool_manager_instance
    if _tool_manager_instance is None:
        _tool_manager_instance = ToolManager()
    return _tool_manager_instance
