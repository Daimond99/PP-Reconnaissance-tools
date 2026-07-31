"""
Recon Tool - Tool Manager Module
Static metadata for the TopBar tool combo — display names for the 6
authorized tools.

This used to spin a background thread on every app launch running
`subprocess.run` against all 6 tools to detect install status + version,
plus 8 getter methods (get_tool_status/get_all_status/get_installed_tools/
get_missing_tools/get_tools_by_category/get_install_guide/get_tool_info/
refresh). Nothing in the GUI ever read any of that — `widgets.py` only
ever pulls `display_name` off `tm.tools.values()` — so it was pure
startup cost (6 blocking subprocess calls) for data nobody consumed.
Trimmed to just what's actually used.
"""

from typing import Dict


class ToolInfo:
    """เก็บข้อมูลของแต่ละ tool"""

    def __init__(self, name: str, display_name: str):
        self.name = name
        self.display_name = display_name


class ToolManager:
    """รายชื่อ tool ที่ authorized ไว้สำหรับ TopBar tool combo"""

    def __init__(self):
        self.tools: Dict[str, ToolInfo] = {
            "nmap": ToolInfo("nmap", "Nmap"),
            "masscan": ToolInfo("masscan", "Masscan"),
            "ncat": ToolInfo("ncat", "Ncat"),
            "hydra": ToolInfo("hydra", "Hydra"),
            "ncrack": ToolInfo("ncrack", "Ncrack"),
            "evil-winrm": ToolInfo("evil-winrm", "Evil-WinRM"),
        }


# สร้าง instance เดียวสำหรับใช้ทั้งโปรแกรม
_tool_manager_instance = None


def get_tool_manager() -> ToolManager:
    """ดึง ToolManager instance"""
    global _tool_manager_instance
    if _tool_manager_instance is None:
        _tool_manager_instance = ToolManager()
    return _tool_manager_instance
