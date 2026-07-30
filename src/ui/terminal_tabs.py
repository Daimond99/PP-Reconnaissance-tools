"""
VS Code-style tabbed terminal container for the Wizard Console.

A thin Qt shell — a `QTabBar` + `QStackedWidget` — over the existing terminal
backends. Each tab is an independent terminal (its own PTY + view). Nothing
about the individual terminal behavior changes; this only lets the user run
several at once.

Two profiles:
  * "wizard" — runs the standalone `chain_wizard` chain CLI (the original
    Wizard Console behavior). The first tab is always a wizard.
  * "shell"  — a plain interactive shell (WSL Ubuntu bash on Windows, bash on
    Linux). `+` opens one of these; the `⌄` menu can open either profile.

Backend selection per terminal is unchanged: XtermTerminal → PtyTerminal →
InteractiveTerminal, first available wins.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QTabBar,
    QToolButton, QLabel, QMenu,
)

from src.config import (
    TERM_BAR, TERM_MUTE, CONSOLE_TEXT, BORDER_SOFT, CONSOLE_BG, PANEL_LIGHT,
    PANEL,
)

# PyCharm-style active-tab accent (orange underline).
_TAB_ACCENT = "#e08a3c"
from src.ui.terminal import InteractiveTerminal
from src.ui.pty_terminal import PtyTerminal, PTY_AVAILABLE
from src.ui.webterm import XtermTerminal, XTERM_AVAILABLE

_WSL_DIR = "/mnt/d/TheRecon/chain_wizard"


def _repo_local_dir() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(repo_root, "chain_wizard")


def make_terminal(profile: str) -> QWidget:
    """Build a terminal widget for `profile` ("wizard" | "shell").

    Same backend fallback chain (Xterm → Pty → Interactive) for both profiles;
    only the launch command differs.
    """
    local_dir = _repo_local_dir()

    if profile == "wizard":
        wsl_launch = f"cd '{_WSL_DIR}' && python3 -m wizard.main; exec bash -l"
        lin_launch = f"cd '{local_dir}' && python3 -m wizard.main; exec bash -l"
    else:  # plain interactive shell
        wsl_launch = "exec bash -l"
        lin_launch = "exec bash -l"

    # 1. xterm.js web terminal — preferred, cross-platform.
    if XTERM_AVAILABLE:
        if os.name == "nt":
            argv = ["wsl.exe", "-d", "Ubuntu", "bash", "-lc", wsl_launch]
        else:
            argv = ["bash", "-lc", lin_launch]
        return XtermTerminal(argv)

    # 2. pyte ConPTY terminal — Windows-only legacy fallback.
    if PTY_AVAILABLE and os.name == "nt":
        return PtyTerminal(["wsl.exe", "-d", "Ubuntu", "bash", "-lc", wsl_launch])

    # 3. plain-pipe fallback — no TTY.
    if os.name == "nt":
        inner = wsl_launch if profile == "shell" else \
            f"cd '{_WSL_DIR}' && python3 -m wizard.main"
        return InteractiveTerminal("wsl.exe", ["-e", "bash", "-lc", inner])
    inner = lin_launch if profile == "shell" else \
        f"cd '{local_dir}' && python3 -m wizard.main"
    return InteractiveTerminal("bash", ["-lc", inner])


class TerminalTabsWidget(QWidget):
    """Tab bar + stack of terminals, VS Code style."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shell_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header (title • tabs • + • ⌄) ────────────────────────────────
        header = QWidget()
        header.setObjectName("TermTabHeader")
        header.setFixedHeight(38)
        hb = QHBoxLayout(header)
        hb.setContentsMargins(0, 0, 8, 0)
        hb.setSpacing(6)

        title = QLabel("Terminal")
        title.setObjectName("TermTabTitle")

        self.tabbar = QTabBar()
        self.tabbar.setObjectName("TermTabBar")
        self.tabbar.setTabsClosable(True)
        self.tabbar.setExpanding(False)     # content-sized tabs, left-aligned
        self.tabbar.setMovable(True)        # drag to reorder
        self.tabbar.setDrawBase(False)
        self.tabbar.setUsesScrollButtons(True)
        self.tabbar.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabbar.tabCloseRequested.connect(self._close_tab)
        self.tabbar.currentChanged.connect(self.stack_set_current)
        self.tabbar.tabMoved.connect(self._on_tab_moved)

        self.add_btn = QToolButton()
        self.add_btn.setObjectName("TermTabBtn")
        self.add_btn.setText("+")
        self.add_btn.setToolTip("New shell tab")
        self.add_btn.setFixedSize(28, 26)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(lambda: self.new_tab("shell"))

        self.menu_btn = QToolButton()
        self.menu_btn.setObjectName("TermTabBtn")
        self.menu_btn.setText("▾")
        self.menu_btn.setToolTip("New terminal by profile")
        self.menu_btn.setFixedSize(28, 26)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.menu_btn)
        menu.setObjectName("TermTabMenu")
        menu.addAction("New Wizard tab", lambda: self.new_tab("wizard"))
        menu.addAction("New Shell tab", lambda: self.new_tab("shell"))
        self.menu_btn.setMenu(menu)

        hb.addWidget(title)
        hb.addSpacing(2)
        hb.addWidget(self.tabbar, 1)
        hb.addWidget(self.add_btn)
        hb.addWidget(self.menu_btn)

        self.stack = QStackedWidget()
        self.stack.setObjectName("TermTabStack")

        root.addWidget(header)
        root.addWidget(self.stack, 1)

        self.setStyleSheet(self._qss())

        # first tab is always the Wizard (preserves original behavior)
        self.new_tab("wizard")

    # -- tab management ----------------------------------------------------
    def new_tab(self, profile: str) -> None:
        term = make_terminal(profile)
        if profile == "wizard":
            name = "Wizard"
        else:
            self._shell_count += 1
            name = "Shell" if self._shell_count == 1 else f"Shell ({self._shell_count})"

        self.stack.addWidget(term)          # stack index == tab index (no reorder)
        idx = self.tabbar.addTab(name)
        self.tabbar.setCurrentIndex(idx)
        self.stack.setCurrentIndex(idx)

    def stack_set_current(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def _on_tab_moved(self, frm: int, to: int) -> None:
        """Keep the stack order aligned with the (drag-reordered) tab bar."""
        w = self.stack.widget(frm)
        if w is None:
            return
        self.stack.removeWidget(w)
        self.stack.insertWidget(to, w)
        self.stack.setCurrentIndex(self.tabbar.currentIndex())

    def _close_tab(self, index: int) -> None:
        if self.tabbar.count() <= 1:
            return  # never close the last terminal
        term = self.stack.widget(index)
        if term is not None:
            stop = getattr(term, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception:
                    pass
            self.stack.removeWidget(term)
            term.deleteLater()
        self.tabbar.removeTab(index)
        cur = self.tabbar.currentIndex()
        self.stack.setCurrentIndex(cur)

    # -- teardown ----------------------------------------------------------
    def stop_all(self) -> None:
        for i in range(self.stack.count()):
            term = self.stack.widget(i)
            stop = getattr(term, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception:
                    pass

    def closeEvent(self, event):
        self.stop_all()
        super().closeEvent(event)

    # -- style -------------------------------------------------------------
    def _qss(self) -> str:
        return f"""
        #TermTabHeader {{
            background: {TERM_BAR};
            border-bottom: 1px solid {BORDER_SOFT};
        }}
        #TermTabStack {{ background: {CONSOLE_BG}; }}
        #TermTabTitle {{
            color: {TERM_MUTE};
            font-size: 12px;
            padding: 0 10px;
        }}
        QTabBar#TermTabBar {{ background: transparent; }}
        QTabBar#TermTabBar::tab {{
            background: transparent;
            color: {TERM_MUTE};
            padding: 6px 10px 6px 12px;
            border: none;
            border-bottom: 2px solid transparent;
        }}
        QTabBar#TermTabBar::tab:hover {{
            background: {PANEL_LIGHT};
            color: {CONSOLE_TEXT};
        }}
        QTabBar#TermTabBar::tab:selected {{
            background: {PANEL};
            color: {CONSOLE_TEXT};
            border-bottom: 2px solid {_TAB_ACCENT};
        }}
        QToolButton#TermTabBtn {{
            color: {TERM_MUTE};
            font-size: 16px;
            font-weight: 700;
            border: none;
            background: transparent;
        }}
        QToolButton#TermTabBtn:hover {{ color: {CONSOLE_TEXT}; }}
        QToolButton#TermTabBtn::menu-indicator {{ image: none; width: 0; }}
        QMenu#TermTabMenu {{
            background: {TERM_BAR};
            color: {CONSOLE_TEXT};
            border: 1px solid {BORDER_SOFT};
            padding: 4px;
        }}
        QMenu#TermTabMenu::item {{ padding: 6px 18px; }}
        QMenu#TermTabMenu::item:selected {{ background: {PANEL_LIGHT}; }}
        """
