"""Recon Tool — Widgets package.

UI components split one-class-per-module (was a single `widgets.py`). The public
names are re-exported here so existing imports (`from src.ui.widgets import
Sidebar, TopBar, ...`) keep working unchanged.
"""

from src.ui.widgets.helpers import svg_icon, wrap_in_terminal
from src.ui.widgets.dropdown import DropdownButton
from src.ui.widgets.sidebar import Sidebar
from src.ui.widgets.topbar import TopBar
from src.ui.widgets.raw_output import RawOutputTab
from src.ui.widgets.results_display import ResultsDisplayTab
from src.ui.widgets.input_management import InputManagementTab
from src.ui.widgets.llm_nmap_panel import LlmNmapPanel
from src.ui.widgets.main_content import MainContentArea, _wizard_console_page

__all__ = [
    "svg_icon",
    "wrap_in_terminal",
    "DropdownButton",
    "Sidebar",
    "TopBar",
    "RawOutputTab",
    "ResultsDisplayTab",
    "InputManagementTab",
    "LlmNmapPanel",
    "MainContentArea",
    "_wizard_console_page",
]
