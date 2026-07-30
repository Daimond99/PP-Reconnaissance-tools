"""Web-based terminal (xterm.js in QWebEngineView) for the Wizard Console.

Public surface: `XtermTerminal` (QWidget) and `XTERM_AVAILABLE`.
"""

from src.ui.webterm.xterm_widget import XtermTerminal, XTERM_AVAILABLE

__all__ = ["XtermTerminal", "XTERM_AVAILABLE"]
