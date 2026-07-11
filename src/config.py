"""
Recon Tool - Configuration Module
เก็บการตั้งค่า, stylesheet และข้อมูลคงที่
"""

WINDOW_TITLE = "Wizard Console Evil-WinRM - Windows Access"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 850
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700

# ============================================================================
# COLOR PALETTE - ตาม Design Reference
# ============================================================================

BG           = "#1e1e1e"
BG_DARKER    = "#161616"
PANEL        = "#262626"
PANEL_LIGHT  = "#2d2d2d"
PURPLE       = "#6b2fa0"
BLUE         = "#2b6fd6"
TEXT         = "#e6e6e6"
TEXT_DIM     = "#9a9a9a"
BORDER       = "#3a3a3a"
CONSOLE_BG   = "#050505"
CONSOLE_TEXT = "#cfcfcf"

# ============================================================================
# STYLESHEET - สไตล์หลักของแอป (แปลงจาก Design Reference)
# ============================================================================

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}

QMenuBar {{
    background-color: {BG_DARKER};
    color: {TEXT};
    padding: 2px 12px;
    font-size: 13px;
    font-weight: 600;
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 14px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {PANEL_LIGHT};
    color: {TEXT};
}}
QMenu {{
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {PURPLE};
    color: #ffffff;
}}

#TopBar {{
    background-color: {BG};
    border-bottom: 1px solid {BORDER};
    min-height: 120px;
}}

#CommandInput {{
    background-color: {PANEL_LIGHT};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 8px 10px;
    border-radius: 4px;
    font-size: 13.5px;
    font-family: 'Courier New', monospace;
}}
#CommandInput:focus {{
    border: 1px solid {BLUE};
}}

#BarLabel {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}

QLineEdit {{
    background-color: {PANEL_LIGHT};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 8px 10px;
    border-radius: 4px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 1px solid {BLUE};
    background-color: #333333;
}}

QComboBox {{
    background-color: {PANEL_LIGHT};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 8px 10px;
    border-radius: 4px;
    font-size: 13px;
    min-width: 160px;
}}
QComboBox:hover {{
    border: 1px solid {BLUE};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL_LIGHT};
    color: {TEXT};
    selection-background-color: {PURPLE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 8px 10px;
    border-radius: 4px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {PANEL};
}}

QPushButton {{
    border-radius: 4px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 700;
}}

#ExecuteButton {{
    background-color: {BLUE};
    color: #ffffff;
    border: none;
    padding: 9px 16px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: 700;
    min-width: 130px;
}}
#ExecuteButton:hover {{
    background-color: #3a7fe0;
}}
#ExecuteButton:pressed {{
    background-color: #1e5bb5;
}}

#BrowseButton {{
    background-color: {BLUE};
    color: #ffffff;
    border: none;
    padding: 9px 16px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: 700;
}}
#BrowseButton:hover {{
    background-color: #3a7fe0;
}}
#BrowseButton:pressed {{
    background-color: #1e5bb5;
}}

#Sidebar {{
    background-color: {BG};
    border-right: 1px solid {BORDER};
    min-width: 240px;
    max-width: 280px;
    padding: 0px;
}}
#SidebarSection {{
    color: {TEXT};
    font-size: 14px;
    font-weight: 600;
    padding: 16px 16px 8px 16px;
    background: transparent;
}}
#SidebarItem {{
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    text-align: left;
    padding: 12px 14px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 6px;
    margin: 2px 16px;
    min-height: 20px;
}}
#SidebarItem:hover {{
    background-color: {PANEL_LIGHT};
    color: {TEXT};
}}
#SidebarItem:pressed {{
    background-color: {PANEL};
}}

QTabWidget::pane {{
    background-color: {BG};
    border: none;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_DIM};
    padding: 14px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 600;
    margin-right: 8px;
}}
QTabBar::tab:selected {{
    color: #ffffff;
    border-bottom: 2px solid {PURPLE};
}}
QTabBar::tab:hover {{
    color: {TEXT};
    background-color: rgba(255, 255, 255, 0.03);
}}

#ConsoleArea {{
    background-color: {CONSOLE_BG};
    color: {CONSOLE_TEXT};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13.5px;
    border: none;
    border-radius: 4px;
    padding: 20px 24px;
}}
#CommandPreviewBox {{
    background-color: {CONSOLE_BG};
    color: {CONSOLE_TEXT};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13.5px;
    padding: 12px 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
}}

#EditCommandArea {{
    background-color: {PANEL_LIGHT};
    color: {TEXT};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    border: 1px solid {BORDER};
    padding: 10px;
    border-radius: 4px;
}}

#ActionButton {{
    background-color: {BLUE};
    color: #ffffff;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: 700;
    min-width: 130px;
}}
#ActionButton:hover {{
    background-color: #3a7fe0;
}}
#ActionButton:pressed {{
    background-color: #1e5bb5;
}}

#InputField {{
    background-color: {PANEL_LIGHT};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 13px;
    min-height: 38px;
}}
#FieldLabel {{
    color: {TEXT};
    font-size: 13px;
    padding: 4px 0;
    font-weight: 600;
}}

#BottomPromptInput {{
    background-color: {BG_DARKER};
    color: {TEXT};
    border: none;
    border-top: 1px solid {BORDER};
    padding: 8px 12px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
}}
#PromptPrefix {{
    color: {TEXT_DIM};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 14px;
    padding: 8px 4px 8px 10px;
    background-color: {BG_DARKER};
    border-top: 1px solid {BORDER};
}}
#PromptFrame {{
    background-color: {BG_DARKER};
    border-top: 1px solid {BORDER};
}}

#HLine {{
    background-color: {BORDER};
    max-height: 1px;
}}

#VLine {{
    background-color: {BORDER};
    max-width: 1px;
}}

#CentralWidget {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

#TitleBar {{
    background-color: {BG_DARKER};
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid {BORDER};
}}
#TitleBarLabel {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}
#WinControlBtn {{
    color: {TEXT_DIM};
    font-size: 14px;
    background: transparent;
    border: none;
    width: 34px;
    height: 24px;
    border-radius: 4px;
}}
#WinControlBtn:hover {{
    background-color: {PANEL_LIGHT};
    color: {TEXT};
}}
#WinControlCloseBtn:hover {{
    background-color: #c0392b;
    color: #ffffff;
}}
"""

# ============================================================================
# WINDOW SETTINGS - การตั้งค่าหน้าต่าง (Removed Old Settings)
# ============================================================================

TERMINAL_FONT_FAMILY = "Consolas"
TERMINAL_FONT_SIZE = 10
TERMINAL_PROMPT = "recon> "

# ============================================================================
# COMMANDS - คำสั่งและ Profiles
# ============================================================================

TOOL_COMMANDS = {
    "Masscan": "masscan -p1-65535 --rate=10000 192.168.1.0/24",
    "Nmap": "nmap -sS -sV -p- 192.168.1.0/24",
    "Ncat": "ncat -v 192.168.1.1 80",
    "Hydra": "hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://192.168.1.1",
    "Ncrack": "ncrack -u admin -P /usr/share/wordlists/rockyou.txt ssh://192.168.1.1",
    "Evil-WinRM": "evil-winrm -i 192.168.1.1 -u Administrator -p password",
    # Legacy display names (backward compatibility)
    "Masscan - Fast Sweep": "masscan -p1-65535 --rate=10000 192.168.1.0/24",
    "Nmap - Detailed Scan": "nmap -sS -sV -p- 192.168.1.0/24",
    "Hybrid Recon": "masscan -p1-65535 --rate=1000 192.168.1.0/24 && nmap -sV -p $(masscan --readformat=file) 192.168.1.0/24",
    "Ncat - Banner Grab": "ncat -v 192.168.1.1 80",
    "Hydra - Brute Force": "hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://192.168.1.1",
    "Ncrack - Credential Test": "ncrack -u admin -P /usr/share/wordlists/rockyou.txt ssh://192.168.1.1",
    "Evil-WinRM - Windows Access": "evil-winrm -i 192.168.1.1 -u Administrator -p password",
}

WARHEAD_COMMANDS = {
    "Stealth Recon": "masscan -p1-65535 --rate=10000 192.168.1.0/24",
    "Full Aggressive": "nmap -A -T4 -p- 192.168.1.0/24",
    "Web Focus": "nmap -sV -p 80,443,8080,8443 192.168.1.0/24",
    "Vulnerability Scan": "nmap --script vuln -sV 192.168.1.0/24",
}

TOOL_LIST = [
    "Masscan - Fast Sweep",
    "Nmap - Detailed Scan",
    "Hybrid Recon",
    "Ncat - Banner Grab",
    "Hydra - Brute Force",
    "Ncrack - Credential Test",
    "Evil-WinRM - Windows Access",
]

WARHEAD_PROFILES = ["Stealth Recon", "Full Aggressive", "Web Focus", "Vulnerability Scan"]

OPERATION_MODES = ["Wizard Mode", "Direct Tool Mode"]

# ============================================================================
# CONTENT TEXT - ข้อความสำหรับแต่ละโหมด
# ============================================================================

DIRECT_TOOL_CONTENT = """\
DIRECT TOOL MODE - Select a Tool

Available Tools:
- Nmap
- Masscan
- Hydra
- Ncrack
- Ncat
- Evil-WinRM

Select tool (or type command):"""

WIZARD_CONTENT = """\
WIZARD MODE - Expert Attack Chain Guide

What do you want to find?

 1. Web Servers
 2. SSH Services
 3. Windows Systems
 4. Databases
 5. Full Network Scan
 6. Custom Scan

Select option (1-6) :"""

LLM_DEMO_TEXT = """\
# Discover your local network
llm --functions llm-tools-nmap.py "What's my local network information?"

# Find live hosts on your network
llm --functions llm-tools-nmap.py "Scan my local network to find live hosts"

# Quick port scan of a hosts in /etc/hosts using pipe capability
cat /etc/hosts | llm --functions llm-tools-nmap.py "Do a quick port scan of these hosts"

# Detailed service detection
llm --functions llm-tools-nmap.py "Scan 192.168.1.1 for services on ports 80,443,22"
"""