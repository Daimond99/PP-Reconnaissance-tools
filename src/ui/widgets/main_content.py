"""MainContentArea — the QStackedWidget holding the 5 sidebar pages, and the
Wizard Console page assembly (control panel + terminal tabs)."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QTabBar,
)

from src.config import PANEL, BORDER_SOFT, CONSOLE_BG, CONSOLE_TEXT, TERM_MUTE, PURPLE
from src.ui.terminal_tabs import TerminalTabsWidget
from src.ui.wizard_panel import WizardControlPanel
from src.ui.widgets.helpers import wrap_in_terminal
from src.ui.widgets.raw_output import RawOutputTab
from src.ui.widgets.results_display import ResultsDisplayTab
from src.ui.widgets.input_management import InputManagementTab
from src.ui.widgets.llm_nmap_panel import LlmNmapPanel


def _wizard_console_page(panel: WizardControlPanel,
                         tabs: TerminalTabsWidget) -> QWidget:
    """Wizard Console page: control panel (left) + terminal tabs (right).
    Panel's scanRequested drives a fresh Wizard tab in the terminal beside
    it — no popup, controls stay visible for re-scans."""
    page = QWidget()
    row = QHBoxLayout(page)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(panel)
    row.addWidget(wrap_in_terminal(tabs), 1)
    panel.scanRequested.connect(tabs.start_wizard_scan)
    return page


def _llm_mode_page(opencode_tab: TerminalTabsWidget, panel: LlmNmapPanel,
                    output_tab: RawOutputTab, llm_tab: TerminalTabsWidget) -> QWidget:
    """LLM Mode page: a top-level tab switcher (one sub-page visible at a
    time, full width) instead of cramming OpenCode + the gated panel + its
    output + the raw LLM Nmap shell into one row of tiny columns — that
    earlier layout is what looked cluttered. Three tabs:
      - "OpenCode" — its own terminal, full width.
      - "LLM Nmap" — the gated suggestion panel + its own output terminal
        (where a confirmed command actually runs — stays on this page
        instead of jumping to Raw Output). `panel` only emits
        `executeRequested`; it never runs anything itself.
      - "LLM Nmap (raw)" — the plain confined `llm` CLI shell, full width.
    """
    page = QWidget()
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    tabbar = QTabBar()
    tabbar.setObjectName("LlmModeTabBar")
    tabbar.addTab("OpenCode")
    tabbar.addTab("LLM Nmap")
    tabbar.addTab("LLM Nmap (raw)")
    tabbar.setDrawBase(False)
    tabbar.setExpanding(False)

    stack = QStackedWidget()

    stack.addWidget(wrap_in_terminal(opencode_tab))

    gated_page = QWidget()
    gated_row = QHBoxLayout(gated_page)
    gated_row.setContentsMargins(0, 0, 0, 0)
    gated_row.setSpacing(0)
    gated_row.addWidget(panel)
    gated_row.addWidget(output_tab, 1)
    stack.addWidget(gated_page)

    stack.addWidget(wrap_in_terminal(llm_tab))

    tabbar.currentChanged.connect(stack.setCurrentIndex)

    root.addWidget(tabbar)
    root.addWidget(stack, 1)
    page.setStyleSheet(f"""
        QTabBar#LlmModeTabBar {{ background: {PANEL}; }}
        QTabBar#LlmModeTabBar::tab {{
            background: {PANEL}; color: {TERM_MUTE};
            padding: 10px 20px; margin: 0; border: none;
            border-right: 1px solid {BORDER_SOFT}; border-radius: 0;
        }}
        QTabBar#LlmModeTabBar::tab:hover {{ color: {CONSOLE_TEXT}; }}
        QTabBar#LlmModeTabBar::tab:selected {{
            background: {CONSOLE_BG}; color: {CONSOLE_TEXT};
            border-bottom: 3px solid {PURPLE};
        }}
    """)
    return page


class MainContentArea(QWidget):
    """พื้นที่หลักสำหรับแสดงหน้าต่างๆ ผ่าน Sidebar navigation เท่านั้น
    (ไม่มี tab bar ซ้ำซ้อน — ตรงกับ mockup)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self._build_pages()
        layout.addWidget(self.stack)

    def _build_pages(self):
        # Wizard Console is a VS Code-style tabbed terminal (TerminalTabsWidget):
        # first tab runs the 'chain_wizard' chain CLI, `+`/`⌄` open more Wizard
        # or plain Shell tabs. Each tab picks its own backend (XtermTerminal →
        # PtyTerminal → InteractiveTerminal). The older native wizard pages
        # (wizard_terminal.py / wizard_console.py / src/wizard/engine.py) were
        # removed — this is the only wizard path now.
        # Wizard Console = control panel (left) + terminal tabs (right).
        # `self.wizard_tab` stays the TerminalTabsWidget so main.py's
        # firstTabReady splash wait and closeEvent's stop_all keep working;
        # the panel drives it via scanRequested → start_wizard_scan.
        self.wizard_tab = TerminalTabsWidget(form_driven=True)
        self.wizard_panel = WizardControlPanel()
        self.input_tab = InputManagementTab()
        self.raw_output_tab = RawOutputTab()
        self.results_tab = ResultsDisplayTab()
        # LLM page — same tabbed-terminal container class as Wizard Console,
        # but each profile now gets its own single-tab column instead of
        # sharing one tab bar (was: one TerminalTabsWidget with both
        # "llm-nmap"/"opencode" profiles; a real tab-switcher wasn't wanted
        # here, so each is now its own always-visible terminal):
        #  - "opencode" (the OpenCode agent CLI, PATH-restricted to
        #    TheRecon's 6 authorized tools — see terminal_tabs._opencode_launch)
        #  - "llm-nmap" (auto-cd's into tools/llm-tools-nmap, offers to set
        #    an API key if none is stored yet)
        # Both ungated by design, same as before (see docs/CURRENT_STATE.md).
        self.opencode_tab = TerminalTabsWidget(fixed=True, profiles=[
            ("New OpenCode tab", "opencode", "OpenCode"),
        ])
        self.llm_tab = TerminalTabsWidget(fixed=True, profiles=[
            ("New LLM Nmap tab", "llm-nmap", "LLM"),
        ])
        # Gated "LLM Nmap" suggestion panel, between the two raw terminals —
        # see _llm_mode_page. Suggestion-only; execution routes through
        # main_window's ConfirmationGate handler via executeRequested.
        self.llm_nmap_panel = LlmNmapPanel()
        # Its own output terminal (separate RawOutputTab instance from
        # Direct Tool Mode's) so a confirmed LLM Nmap command streams live
        # right here on the LLM Mode page instead of switching pages.
        self.llm_output_tab = RawOutputTab()

        # Order matches Sidebar.NAV_ITEMS / navigate(index) 0-4.
        self.stack.addWidget(_wizard_console_page(self.wizard_panel, self.wizard_tab))
        self.stack.addWidget(self.input_tab)
        self.stack.addWidget(self.raw_output_tab)
        self.stack.addWidget(self.results_tab)
        self.stack.addWidget(_llm_mode_page(
            self.opencode_tab, self.llm_nmap_panel, self.llm_output_tab, self.llm_tab))
