"""MainContentArea — the QStackedWidget holding the 5 sidebar pages, and the
Wizard Console page assembly (control panel + terminal tabs)."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget

from src.ui.terminal_tabs import TerminalTabsWidget
from src.ui.wizard_panel import WizardControlPanel
from src.ui.widgets.helpers import wrap_in_terminal
from src.ui.widgets.raw_output import RawOutputTab
from src.ui.widgets.results_display import ResultsDisplayTab
from src.ui.widgets.input_management import InputManagementTab


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
        # LLM page — same tabbed-terminal container as Wizard Console, two
        # profiles instead: "llm-nmap" (auto-cd's into tools/llm-tools-nmap,
        # offers to set an API key if none is stored yet) and "opencode"
        # (the OpenCode agent CLI, PATH-restricted to TheRecon's 6
        # authorized tools — see terminal_tabs._opencode_launch). Ungated by
        # design, same as before.
        self.llm_tab = TerminalTabsWidget(fixed=True, profiles=[
            ("New LLM Nmap tab", "llm-nmap", "LLM"),
            ("New OpenCode tab", "opencode", "OpenCode"),
        ])

        # Order matches Sidebar.NAV_ITEMS / navigate(index) 0-4.
        self.stack.addWidget(_wizard_console_page(self.wizard_panel, self.wizard_tab))
        self.stack.addWidget(self.input_tab)
        self.stack.addWidget(self.raw_output_tab)
        self.stack.addWidget(self.results_tab)
        self.stack.addWidget(wrap_in_terminal(self.llm_tab))
