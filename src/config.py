"""
Recon Tool - Configuration Module
เก็บการตั้งค่า, stylesheet และข้อมูลคงที่
"""

WINDOW_TITLE = "Wizard Console Evil-WinRM - Windows Access"
WINDOW_WIDTH = 1080
WINDOW_HEIGHT = 760
WINDOW_MIN_WIDTH = 860
WINDOW_MIN_HEIGHT = 580

# ============================================================================
# COLOR PALETTE - ตาม Design Reference
# ============================================================================

BG           = "#282a36"
BG_DARKER    = "#21222c"
PANEL        = "#303241"
PANEL_LIGHT  = "#3a3d4d"
PURPLE       = "#bd93f9"
BLUE         = "#bd93f9"
TEXT         = "#f8f8f2"
TEXT_DIM     = "#b8b8c4"
BORDER       = "#44475a"
CONSOLE_BG   = "#050505"
CONSOLE_TEXT = "#f8f8f2"

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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(48, 55, 67, 230), stop:1 rgba(34, 39, 48, 230));
    border: 1px solid rgba(103, 116, 135, 105);
    border-top: 1px solid rgba(212, 220, 235, 48);
    border-radius: 12px;
    min-height: 106px;
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
    background-color: {BG};
    border: 1px solid #16191e;
    border-top: 1px solid #343b47;
    color: {TEXT};
    padding: 9px 12px;
    border-radius: 10px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 1px solid {BLUE};
    background-color: #333333;
}}

QComboBox {{
    background-color: {PANEL};
    border: 1px solid #171a20;
    border-top: 1px solid #3a4350;
    color: {TEXT};
    padding: 8px 10px;
    border-radius: 10px;
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #333a46, stop:1 #272d36);
    color: {TEXT};
    border: 1px solid #171a20;
    border-top: 1px solid #3e4754;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 700;
}}

#ContentCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(48, 54, 65, 238), stop:1 rgba(36, 41, 50, 238));
    border: 1px solid rgba(113, 126, 145, 110);
    border-top: 1px solid rgba(196, 207, 224, 62);
    border-radius: 12px;
}}
#SearchInput {{
    background-color: {BG};
    border: 1px solid #16191e;
    border-top: 1px solid #343b47;
    border-radius: 10px;
    padding: 9px 12px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3b4452, stop:1 #2c333e);
    border-top-color: #4a5666;
}}
QPushButton:pressed {{
    background-color: #1c2027;
    border-top-color: #171a20;
    border-bottom-color: #3a4350;
    padding-top: 10px;
    padding-bottom: 8px;
}}

#ExecuteButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #718ddd, stop:1 #4e6ab8);
    color: #ffffff;
    border: 1px solid #31457d;
    border-top: 1px solid #8199dc;
    padding: 9px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    min-width: 130px;
}}
#ExecuteButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #819be5, stop:1 #5c79c8);
}}
#ExecuteButton:pressed {{
    background-color: #405a9d;
}}

#BrowseButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #333a46, stop:1 #272d36);
    color: {TEXT};
    border: 1px solid #171a20;
    border-top: 1px solid #3e4754;
    padding: 9px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
}}
#BrowseButton:hover {{
    background-color: #323945;
}}
#BrowseButton:pressed {{
    background-color: #1c2027;
}}

#Sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(45, 51, 62, 248), stop:1 rgba(34, 39, 47, 248));
    border-right: 1px solid #15181d;
    min-width: 210px;
    max-width: 250px;
    padding: 0px;
}}
#SidebarSection {{
    color: {TEXT};
    font-size: 14px;
    font-weight: 600;
    padding: 16px 16px 8px 16px;
    background: transparent;
}}
#ChatItem {{
    background-color: transparent;
    border: none;
    color: {TEXT_DIM};
    text-align: left;
    padding: 9px 10px;
    border-radius: 8px;
    font-weight: 500;
}}
#ChatItem:hover {{ background-color: #343b47; color: {TEXT}; }}
#SidebarItem {{
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid #171a20;
    border-top: 1px solid #3e4754;
    text-align: left;
    padding: 12px 14px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    margin: 2px 0;
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
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid #171a20;
    border-top: 1px solid #3e4754;
    padding: 10px 20px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
    min-width: 130px;
}}
#ActionButton:hover {{
    background-color: #323945;
}}
#ActionButton:pressed {{
    background-color: #1c2027;
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
#TitleMark {{
    background-color: #516fc0;
    color: white;
    border-radius: 9px;
    font-weight: 800;
    padding: 3px 8px;
}}
#TitleBarLabel {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}
#WinControlBtn {{
    color: {TEXT_DIM};
    font-size: 14px;
    background: {PANEL};
    border: 1px solid #171a20;
    border-top: 1px solid #3e4754;
    width: 30px;
    height: 26px;
    border-radius: 8px;
}}
#WinControlBtn:hover {{
    background-color: {PANEL_LIGHT};
    color: {TEXT};
}}
#WinControlCloseBtn:hover {{
    background-color: #c0392b;
    color: #ffffff;
}}

/* Dracula theme overrides: visual styling only, no layout changes. */
QMainWindow, QWidget {{
    background-color: #282a36;
    color: #f8f8f2;
}}
QLabel {{ color: #f8f8f2; }}
QMenuBar, QMenu {{
    background-color: #282a36;
    color: #f8f8f2;
    border-color: #44475a;
}}
QMenu::item:selected {{ background-color: #44475a; color: #f8f8f2; }}
QPushButton {{
    background-color: #303241;
    color: #f8f8f2;
    border: 1px solid #44475a;
    border-radius: 7px;
}}
QPushButton:hover {{ background-color: #44475a; border-color: #6272a4; }}
QPushButton:pressed {{ background-color: #252633; border-color: #bd93f9; }}
#ExecuteButton, #ActionButton {{
    background-color: #6272a4;
    color: #f8f8f2;
    border: 1px solid #bd93f9;
    border-radius: 7px;
}}
#ExecuteButton:hover, #ActionButton:hover {{ background-color: #7182b5; }}
#ExecuteButton:pressed, #ActionButton:pressed {{ background-color: #4f5c83; }}
#BrowseButton, #SidebarItem {{
    background-color: #303241;
    color: #f8f8f2;
    border: 1px solid #44475a;
    border-radius: 7px;
}}
#BrowseButton:hover, #SidebarItem:hover {{ background-color: #44475a; border-color: #6272a4; }}
#BrowseButton:pressed, #SidebarItem:pressed {{ background-color: #252633; }}
#SidebarItem:checked, #SidebarItem[selected="true"] {{
    border-left: 3px solid #bd93f9;
    background-color: #44475a;
}}
QLineEdit, #CommandInput, #SearchInput, QTextEdit#EditCommandArea {{
    background-color: #282a36;
    color: #f8f8f2;
    border: 1px solid #44475a;
    border-radius: 7px;
}}
QLineEdit:focus, #CommandInput:focus, #SearchInput:focus, QTextEdit#EditCommandArea:focus {{
    border: 1px solid #bd93f9;
}}
QComboBox {{
    background-color: #303241;
    color: #f8f8f2;
    border: 1px solid #44475a;
    border-radius: 7px;
    padding: 8px 10px;
}}
QComboBox:hover {{ border-color: #6272a4; }}
QComboBox:focus {{ border-color: #bd93f9; }}
QComboBox::drop-down {{ border-left: 1px solid #44475a; width: 26px; }}
QComboBox QAbstractItemView, QListWidget {{
    background-color: #282a36;
    color: #f8f8f2;
    border: 1px solid #44475a;
    border-radius: 7px;
    outline: none;
    padding: 3px;
}}
QComboBox QAbstractItemView::item, QListWidget::item {{
    min-height: 22px;
    padding: 8px 10px;
    border-bottom: 1px solid #44475a;
}}
QComboBox QAbstractItemView::item:hover, QListWidget::item:hover {{ background-color: #44475a; }}
QComboBox QAbstractItemView::item:selected, QListWidget::item:selected {{
    background-color: #bd93f9;
    color: #282a36;
    border-left: 3px solid #bd93f9;
}}
QTabWidget::pane {{ background-color: #282a36; border: 1px solid #44475a; border-radius: 7px; }}
QTabBar::tab {{
    background-color: #303241;
    color: #b8b8c4;
    border: 1px solid #44475a;
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}}
QTabBar::tab:hover {{ background-color: #44475a; color: #f8f8f2; }}
QTabBar::tab:selected {{ background-color: #282a36; color: #f8f8f2; border-top: 2px solid #bd93f9; }}
#Sidebar, #TopBar, #ContentCard, #TitleBar {{ background-color: #282a36; border-color: #44475a; }}
#ConsoleArea, QTextEdit {{ background-color: #050505; color: #f8f8f2; }}
#CommandPreviewBox {{ background-color: #050505; color: #f8f8f2; border-color: #44475a; border-radius: 7px; }}
#WinControlCloseBtn:hover {{ background-color: #44475a; color: #f8f8f2; }}
QStatusBar, #StatusBar {{ max-height: 0px; min-height: 0px; border: none; padding: 0; }}
#StatusBar {{
    background-color: {BG_DARKER};
    border-top: 1px solid #101216;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}}
#StatusLabel {{ color: {TEXT_DIM}; font-size: 12px; padding: 0 12px; }}
#StatusDot {{ color: #61c28b; font-size: 14px; padding-left: 12px; }}
QToolButton#IconButton {{
    background-color: {PANEL};
    border: 1px solid #171a20;
    border-top: 1px solid #3e4754;
    border-radius: 8px;
    padding: 5px;
}}
QToolButton#IconButton:hover {{ background-color: #343b47; }}
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

# ============================================================================
# LLM MODE - Scope, credential store, and AI provider configuration
# ============================================================================

# Sandbox/lab scope that every LLM-suggested target must fall inside before
# the Confirmation Gate will even build a preview. Adjust to your authorized
# test range.
AUTHORIZED_SCOPE = "192.168.1.0/24"

# Name under which API keys are namespaced in the OS credential store
# (Windows Credential Manager / macOS Keychain / Secret Service on Linux).
KEYRING_SERVICE_NAME = "TheRecon"

# Path to the llm-tools-nmap.py functions file used with `llm --functions`.
# Download from: https://github.com/peter-hackertarget/llm-tools-nmap
# Defaults to the project root; change this if you keep it elsewhere.
LLM_TOOLS_NMAP_PATH = "llm-tools-nmap.py"

AI_MODE_PROVIDERS = {
    "openai": {
        "label": "OpenAI (GPT-4o-mini)",
        "keyring_key": "openai_api_key",
        "env_var": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "keyring_key": "anthropic_api_key",
        "env_var": "ANTHROPIC_API_KEY",
        "model": "claude-3-5-sonnet-latest",
    },
}

# System prompt sent with EVERY AI Mode (`llm -s ...`) call. Keeps the model
# scoped to nmap-based network recon only and unable to drift into general
# conversation, other tools, or auto-execution.
SYSTEM_PROMPT = """\
คุณคือ Network Recon Assistant สำหรับโปรแกรม TheRecon เท่านั้น
หน้าที่ของคุณคือช่วยแปลงคำขอภาษาคนของผู้ใช้ให้เป็นคำสั่ง nmap ที่เหมาะสม
ผ่าน function ที่มีอยู่ใน llm-tools-nmap plugin เท่านั้น (nmap_quick_scan,
nmap_port_scan, nmap_service_detection, nmap_os_detection, nmap_ping_scan,
nmap_script_scan, nmap_scan)

กฎเคร่งครัดที่ต้องปฏิบัติตามเสมอ:
1. ตอบเฉพาะเรื่อง network scanning, port enumeration, service/OS detection
   ที่เกี่ยวข้องกับ nmap เท่านั้น
2. ถ้าผู้ใช้ถามเรื่องอื่นที่ไม่เกี่ยวกับ network recon (เช่น คำถามทั่วไป,
   เขียนโค้ดเรื่องอื่น, สนทนาเล่น) ให้ตอบกลับว่า:
   "ขออภัย ผมสามารถช่วยเฉพาะเรื่อง network reconnaissance ผ่าน nmap เท่านั้น
   กรุณาระบุคำขอที่เกี่ยวข้องกับการสแกนเครือข่าย"
3. ห้ามแนะนำหรือรันคำสั่งใดๆ ที่ไม่ใช่ nmap function ที่กำหนดไว้
   (ห้าม suggest เครื่องมืออื่นนอกเหนือจากที่ระบบอนุญาต แม้จะรู้จักก็ตาม)
4. ห้าม generate คำสั่งที่มี target อยู่นอกขอบเขต scope ที่ผู้ใช้ระบุไว้ต้นโปรแกรม
5. ทุกคำสั่งที่แนะนำต้องมาพร้อมคำอธิบายสั้นๆ ว่าทำอะไร เพื่อให้ผู้ใช้ตัดสินใจ
   ก่อน confirm ได้ง่าย
6. ห้ามรันคำสั่งเองโดยตรง มีหน้าที่แค่ "แนะนำ" คำสั่งเท่านั้น ระบบจะเป็นผู้
   ดำเนินการรันจริงหลังผู้ใช้ยืนยันผ่าน Confirmation Gate
"""

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
