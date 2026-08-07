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
PURPLE_DIM   = "#8c6fd1"
PURPLE_SOFT  = "#362b52"
BLUE         = "#bd93f9"
TEXT         = "#f8f8f2"
TEXT_DIM     = "#b8b8c4"
BORDER       = "#44475a"
CONSOLE_BG   = "#050505"
CONSOLE_TEXT = "#f8f8f2"

# Mission Control mockup palette — used by the sidebar / mission bar /
# terminal chrome / Zenmap-style Results Display introduced to match
# Mockup HTML.txt.
BG_APP       = "#21222c"
BG_PANEL_2   = "#2f3140"
BG_INPUT     = "#191a21"
BORDER_SOFT  = "#34364a"
TEXT_MUTE    = "#6272a4"
ORANGE       = "#ffb86c"
TERM_BG      = "#0c0c0e"
TERM_BAR     = "#151318"
TERM_MUTE    = "#7a7a85"

# Terminal accent colors (Dracula-consistent) — used to colorize console
# output / status text by message type (success, error).
ACCENT_GREEN  = "#50fa7b"
ACCENT_RED    = "#ff5555"

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
    padding: 3px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 5px 8px;
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
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 600;
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
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
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
#WinControlBtn, #WinControlCloseBtn {{
    color: {TEXT};
    background: transparent;
    border: none;
    min-width: 40px;
    max-width: 40px;
    min-height: 30px;
    border-radius: 6px;
}}
#WinControlBtn:hover {{
    background-color: {PANEL_LIGHT};
}}
#WinControlCloseBtn:hover {{
    background-color: #e81123;
}}
#TitleDragArea {{ background: transparent; }}
#TitleToolBtn {{
    color: {TEXT};
    background: transparent;
    border: none;
    min-width: 34px;
    max-width: 34px;
    min-height: 30px;
    border-radius: 6px;
}}
#TitleToolBtn:hover {{ background-color: {PANEL_LIGHT}; }}
#TitleSettingsBtn {{
    color: {TEXT};
    background: transparent;
    border: none;
    min-height: 30px;
    padding: 0 8px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 600;
}}
#TitleSettingsBtn:hover {{ background-color: {PANEL_LIGHT}; color: {PURPLE}; }}

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
#MissionCombo {{ text-align: left; padding: 8px 10px; }}
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
    min-height: 18px;
    padding: 5px 8px;
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
#WinControlCloseBtn:hover {{ background-color: #e81123; color: #ffffff; }}
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

/* ============================================================
   Mission Control mockup chrome — sidebar nav, mission bar,
   terminal windows, Zenmap-style Results Display.
   ============================================================ */

#Sidebar {{
    background-color: {BG_PANEL_2};
    border-right: 1px solid {BORDER_SOFT};
    min-width: 160px;
    max-width: 420px;
}}
QSplitter#BodySplitter::handle {{
    background-color: {BORDER};
}}
QSplitter#BodySplitter::handle:hover {{
    background-color: {PURPLE};
}}
#Sidebar[collapsed="true"] {{
    min-width: 68px;
    max-width: 68px;
}}
#SidebarToggle {{
    background: transparent;
    border: none;
    color: {TEXT_DIM};
    font-size: 18px;
    border-radius: 6px;
}}
#SidebarToggle:hover {{ background-color: {BG_PANEL_2}; color: {PURPLE}; }}
#SidebarNavItem {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    color: {TEXT_DIM};
    text-align: left;
    padding: 10px 10px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}}
#SidebarNavItem:hover {{ background-color: {BG_PANEL_2}; color: {TEXT}; }}
#SidebarNavItem[selected="true"] {{
    background-color: {PURPLE_SOFT};
    border-left: 3px solid {PURPLE};
    color: {PURPLE};
}}
#SidebarSettingsItem {{
    background: transparent;
    border: none;
    color: {TEXT_MUTE};
    text-align: left;
    padding: 10px 10px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}}
#SidebarSettingsItem:hover {{ background-color: {BG_PANEL_2}; color: {TEXT}; }}

#MissionBar {{
    background-color: {BG_PANEL_2};
    border-bottom: 1px solid {BORDER_SOFT};
}}
#MissionFieldLabel {{
    color: {TEXT_DIM};
    background: transparent;
    border: none;
    font-size: 10px;
    font-weight: 600;
}}
#MissionInput, #MissionCombo {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    color: {TEXT};
    border-radius: 7px;
    padding: 8px 10px;
    font-size: 13px;
}}
#MissionInput:focus, #MissionCombo:focus {{ border: 1px solid {PURPLE_DIM}; }}
#CmdPreview {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    color: {PURPLE};
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12.5px;
    padding: 10px 14px;
}}
#CmdPreview:focus {{ border: 1px solid {PURPLE_DIM}; }}

#TermWindow {{
    background-color: {TERM_BG};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
}}
#TermBar {{
    background-color: {TERM_BAR};
    border-bottom: 1px solid #201f26;
}}
#TermIcon, #TermTitle {{
    color: {TERM_MUTE};
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 11.5px;
}}

#LogStatus {{
    color: {ORANGE};
    font-size: 12.5px;
    font-weight: 600;
}}
#LogStatus[running="true"] {{ color: {ACCENT_GREEN}; }}
#LogStatusDot {{
    color: {ORANGE};
    font-size: 16px;
}}
#LogStatusDot[running="true"] {{ color: {ACCENT_GREEN}; }}

#ZmHostList {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
    outline: none;
    padding: 4px;
}}
#ZmHostList::item {{
    padding: 8px 10px;
    border-radius: 6px;
    color: {TEXT_DIM};
}}
#ZmHostList::item:hover {{ background-color: {BG_PANEL_2}; }}
#ZmHostList::item:selected {{
    background-color: {PURPLE_SOFT};
    color: {TEXT};
}}
#ZmDetailTree {{
    background-color: {BG_PANEL_2};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
    outline: none;
    padding: 4px;
}}
#ZmDetailTree::item {{ padding: 5px 4px; color: {TEXT_DIM}; }}
#ZmDetailTree::item:selected {{ background-color: transparent; color: {TEXT_DIM}; }}
#ZmKeyLabel {{ color: {TEXT_MUTE}; font-size: 12.5px; }}
#ZmValueLabel {{ color: {TEXT_DIM}; font-size: 12.5px; }}
#ZmAccuracyBar {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
#ZmAccuracyLabel {{ color: #1c1d26; font-size: 10.5px; font-weight: 700; }}
"""

# ============================================================================
# WINDOW SETTINGS - การตั้งค่าหน้าต่าง (Removed Old Settings)
# ============================================================================

TERMINAL_FONT_FAMILY = "Consolas"
TERMINAL_FONT_SIZE = 10
TERMINAL_PROMPT = "recon> "
