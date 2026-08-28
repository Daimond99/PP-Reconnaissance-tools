"""
VS Code-style tabbed terminal container, used by the LLM Mode page
("opencode" / "llm-nmap" profiles, `fixed=True`) and available for a plain
interactive shell ("shell" profile).

A thin Qt shell — a `QTabBar` + `QStackedWidget` — over the existing terminal
backends. Each tab is an independent terminal (its own PTY + view). Nothing
about the individual terminal behavior changes; this only lets the user run
several at once.

The Wizard Console no longer uses this widget — it runs the `chain_wizard`
subprocess hidden (`--gui`, plain pipes) and drives it entirely through Qt
dialogs (`src/ui/wizard_runner.py`, `wizard_dialogs.py`), not a terminal.

Backend selection per terminal is unchanged: XtermTerminal → PtyTerminal →
InteractiveTerminal, first available wins.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QTabBar,
    QToolButton, QLabel, QMenu,
)

from src.config import (
    TERM_BAR, TERM_MUTE, CONSOLE_TEXT, BORDER_SOFT, CONSOLE_BG, PANEL_LIGHT,
    PANEL, PURPLE, PURPLE_DIM,
)

# PyCharm-style active-tab accent (orange underline).
_TAB_ACCENT = "#e08a3c"
from src.ui.terminal import InteractiveTerminal
from src.ui.pty_terminal import PtyTerminal, PTY_AVAILABLE
from src.ui.webterm import XtermTerminal, XTERM_AVAILABLE
# Pure launch-script + path builders (no Qt) — split out so they're testable.
from src.ui.terminal_launch import (
    _repo_root_dir, _repo_local_llm_dir, _repo_local_opencode_dir,
    _wsl_root_dir, _wsl_llm_dir, _wsl_opencode_dir,
    _shell_launch, _llm_launch, _opencode_launch,
)

# Each tab is a separate QWebEngineView = a separate Chromium renderer
# process (plus its own wsl.exe/bash PTY) — capping how many can be open at
# once keeps the app usable on lower-spec machines instead of letting the
# user pile up processes until the machine chokes.
_MAX_TABS = 4

# Pseudo-distros WSL lists that are never a real Linux userspace to launch a
# shell in — Docker Desktop registers these even if the user never touches
# WSL directly.
_WSL_PSEUDO_DISTROS = {"docker-desktop", "docker-desktop-data"}

# Cached across every terminal spawned this run — checking the distro list
# is a real subprocess round-trip, not worth repeating per tab.
_wsl_checked: bool | None = None


def _wsl_available() -> bool:
    """Windows-only: is `wsl.exe` on PATH AND at least one real distro
    registered? Deliberately not tied to any distro name (Ubuntu, Debian,
    Kali, ...) — whatever the user has installed and set as their WSL
    default is used via `wsl.exe` with no `-d` flag. This app has no
    installer step for WSL itself (a Windows feature + reboot, out of scope
    for anything this app can do unattended) — this check exists purely so
    a missing WSL shows a clear message instead of a silently blank
    terminal."""
    global _wsl_checked
    if _wsl_checked is not None:
        return _wsl_checked
    _wsl_checked = False
    if shutil.which("wsl.exe"):
        try:
            result = subprocess.run(
                ["wsl.exe", "-l", "-q"], capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # wsl.exe emits UTF-16LE (with stray NULs) even when piped.
            listed = result.stdout.decode("utf-16-le", "ignore").replace("\x00", "")
            distros = {line.strip() for line in listed.splitlines() if line.strip()}
            if distros - _WSL_PSEUDO_DISTROS:
                _wsl_checked = True
        except Exception:
            pass
    return _wsl_checked


def _wsl_missing_widget() -> QWidget:
    """Plain placeholder shown instead of a terminal when no usable WSL
    distro is registered. Deliberately has none of the terminal methods
    (run_command/stop/focus/...) — every caller reaches those through
    `getattr(..., None)` + `callable()` guards, so a plain widget here is
    safe everywhere a real terminal would otherwise go."""
    from src.config import CONSOLE_BG, CONSOLE_TEXT

    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label = QLabel(
        "No WSL2 Linux distro found.\n\n"
        "This app runs its tools (nmap, hydra, ...) inside WSL2 on Windows.\n"
        "Install one, then restart this app:\n\n"
        "    wsl --install\n\n"
        "(first-time install needs a reboot; any distro works as long as\n"
        "the 6 tools are installed in it and it's set as your WSL default)"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {CONSOLE_TEXT}; padding: 24px; font-size: 13px;")
    layout.addWidget(label)
    w.setStyleSheet(f"background-color: {CONSOLE_BG};")
    return w


def make_terminal(profile: str, read_only: bool = False) -> QWidget:
    """Build a terminal widget for `profile` ("shell" | "llm-nmap" |
    "opencode").

    Same backend fallback chain (Xterm → Pty → Interactive) for all
    profiles; only the launch command differs. "llm-nmap" auto-cd's into
    the llm-tools-nmap plugin dir and offers to set an API key if none is
    stored yet. "opencode" launches the OpenCode agent CLI with its PATH
    restricted to TheRecon's 6 authorized tools (see `_opencode_launch`).

    `read_only=True` (Raw Output) drops every keystroke/paste from the page
    before it reaches the PTY -- display-only, real output still streams
    in, and `write_text`/`run_command` (Direct Tool Mode's programmatic
    command injection) are untouched since they write to the backend
    directly rather than through the same path as page keystrokes. Only
    the Xterm (tier 1) and Pty (tier 2) backends support this; the
    plain-pipe fallback (tier 3) does not and is not expected to be hit on
    a machine where WebEngine/ConPTY are available.
    """
    if os.name == "nt" and not _wsl_available():
        return _wsl_missing_widget()

    if profile == "llm-nmap":
        wsl_launch = _llm_launch(_wsl_llm_dir())
        lin_launch = _llm_launch(_repo_local_llm_dir())
    elif profile == "opencode":
        wsl_launch = _opencode_launch(_wsl_opencode_dir())
        lin_launch = _opencode_launch(_repo_local_opencode_dir())
    else:  # plain interactive shell — opencode blocked, see _shell_launch()
        wsl_launch = _shell_launch(_wsl_root_dir())
        lin_launch = _shell_launch(_repo_root_dir())

    # 1. xterm.js web terminal — preferred, cross-platform.
    if XTERM_AVAILABLE:
        if os.name == "nt":
            # `-e` (--exec) matters, not just style: without it, wsl.exe
            # re-parses "bash -lc <script>" through an extra shell layer
            # that silently breaks multi-statement scripts — variable
            # assignments stop persisting across `;`-separated commands
            # (confirmed: `OC=x; [ -z "$OC" ] && echo BUG` prints BUG
            # without `-e`, correctly doesn't with it). Harmless for the
            # simple one-liner "shell" launch, but silently broke
            # "llm-nmap"/"opencode"'s multi-step setup scripts.
            argv = ["wsl.exe", "-e", "bash", "-lc", wsl_launch]  # default distro
        else:
            argv = ["bash", "-lc", lin_launch]
        return XtermTerminal(argv, block_ctrl_z=(profile == "opencode"), read_only=read_only)

    # 2. pyte ConPTY terminal — Windows-only legacy fallback.
    if PTY_AVAILABLE and os.name == "nt":
        return PtyTerminal(["wsl.exe", "-e", "bash", "-lc", wsl_launch], read_only=read_only)

    # 3. plain-pipe fallback — no TTY.
    if os.name == "nt":
        return InteractiveTerminal("wsl.exe", ["-e", "bash", "-lc", wsl_launch])
    return InteractiveTerminal("bash", ["-lc", lin_launch])


class TerminalTabsWidget(QWidget):
    """Tab bar + stack of terminals, VS Code style."""

    # Emitted once the first (Wizard) tab's shell has actually produced its
    # first output — i.e. WSL finished booting and bash is really running,
    # not just that `wsl.exe` was spawned (that returns immediately, well
    # before the VM finishes booting). Fires immediately for tabs with no
    # such async concept (fallback terminal, or the WSL-missing
    # placeholder). Startup can wait on this to keep a splash screen up
    # until WSL is genuinely usable, not just until widget construction
    # returns.
    firstTabReady = Signal()

    # (menu label, profile key, tab base name). First entry is the "+"
    # button's target and the always-open first tab. Callers (the LLM Mode
    # page) pass their own profile list; this is just the generic fallback
    # for a plain shell terminal.
    _DEFAULT_PROFILES = [
        ("New Shell tab", "shell", "Shell"),
    ]

    def __init__(self, parent=None, profiles=None, fixed=False):
        """`fixed=True` opens exactly one tab per entry in `profiles`, up
        front, and permanently disables `+`/`⌄` — no more tabs, ever, of any
        profile. Used for pages where a second instance of a profile can't
        run safely (OpenCode locks its workspace dir; a second tab just
        hangs) instead of relying on the shared `_MAX_TABS` cap."""
        super().__init__(parent)
        self._profiles = profiles or self._DEFAULT_PROFILES
        self._profile_names = {key: name for _, key, name in self._profiles}
        self._tab_counts: dict = {}
        self._fixed = fixed

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header (title • tabs • + • ⌄) ────────────────────────────────
        header = QWidget()
        header.setObjectName("TermTabHeader")
        header.setFixedHeight(38)
        hb = QHBoxLayout(header)
        hb.setContentsMargins(0, 0, 0 if self._fixed else 8, 0)
        hb.setSpacing(0 if self._fixed else 6)

        title = QLabel("Terminal")
        title.setObjectName("TermTabTitle")
        if self._fixed:
            # Fixed mode is two big square-cornered blocks, not compact
            # pill tabs next to a title — the title label would just eat
            # into the width the blocks are supposed to fill.
            title.setVisible(False)
            header.setFixedHeight(44)

        self.tabbar = QTabBar()
        self.tabbar.setObjectName("TermTabBar")
        self.tabbar.setProperty("blockStyle", self._fixed)
        self.tabbar.setTabsClosable(not self._fixed)
        # Fixed mode: tabs expand to split the full width evenly, like two
        # big side-by-side buttons, instead of content-sized pills.
        self.tabbar.setExpanding(self._fixed)
        self.tabbar.setMovable(not self._fixed)  # drag to reorder
        self.tabbar.setDrawBase(False)
        self.tabbar.setUsesScrollButtons(True)
        self.tabbar.setElideMode(Qt.TextElideMode.ElideRight)
        if self._fixed:
            self.tabbar.setFixedHeight(44)
        self.tabbar.tabCloseRequested.connect(self._close_tab)
        self.tabbar.currentChanged.connect(self.stack_set_current)
        self.tabbar.tabMoved.connect(self._on_tab_moved)

        self.add_btn = QToolButton()
        self.add_btn.setObjectName("TermTabBtn")
        self.add_btn.setText("+")
        self.add_btn.setToolTip(self._profiles[0][0])
        self.add_btn.setFixedSize(28, 26)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(lambda: self.new_tab(self._profiles[0][1]))

        self.menu_btn = QToolButton()
        self.menu_btn.setObjectName("TermTabBtn")
        self.menu_btn.setText("▾")
        self.menu_btn.setToolTip("New terminal by profile")
        self.menu_btn.setFixedSize(28, 26)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.menu_btn)
        menu.setObjectName("TermTabMenu")
        for label, profile_key, _name in self._profiles:
            menu.addAction(label, lambda p=profile_key: self.new_tab(p))
        self.menu_btn.setMenu(menu)

        hb.addWidget(title)
        hb.addSpacing(2)
        hb.addWidget(self.tabbar, 1)
        if not self._fixed:
            hb.addWidget(self.add_btn)
            hb.addWidget(self.menu_btn)
        else:
            self.add_btn.setVisible(False)
            self.menu_btn.setVisible(False)

        self.stack = QStackedWidget()
        self.stack.setObjectName("TermTabStack")

        root.addWidget(header)
        root.addWidget(self.stack, 1)

        self.setStyleSheet(self._qss())

        self._first_tab_wired = False
        if self._fixed:
            # exactly one tab per profile, opened up front, no `+`/`⌄` to
            # ever add another — some profiles (OpenCode) hang if a second
            # instance runs against the same workspace dir, so the fix is
            # to make a second instance impossible rather than recoverable.
            for _label, profile_key, _name in self._profiles:
                self.new_tab(profile_key)
        else:
            # first tab always uses the caller's first profile (Shell by
            # default)
            self.new_tab(self._profiles[0][1])

    # -- tab management ----------------------------------------------------
    def new_tab(self, profile: str) -> None:
        if self.tabbar.count() >= _MAX_TABS:
            # Refuse before make_terminal() ever runs — that's what actually
            # spawns the Chromium process + PTY, so the cap has to gate here,
            # not just disable the buttons (belt-and-suspenders against any
            # other caller reaching new_tab directly).
            return
        term = make_terminal(profile)
        base_name = self._profile_names.get(profile, profile)
        count = self._tab_counts.get(profile, 0) + 1
        self._tab_counts[profile] = count
        name = base_name if count == 1 else f"{base_name} ({count})"

        if not self._first_tab_wired:
            self._first_tab_wired = True
            ready_signal = getattr(term, "firstOutput", None)
            if ready_signal is not None:
                ready_signal.connect(self.firstTabReady.emit)
            else:
                # No async spawn concept (PtyTerminal/InteractiveTerminal
                # spawn synchronously in their constructor; the WSL-missing
                # placeholder has nothing to wait for) — fire on the next
                # event-loop tick so callers can always just connect+wait.
                QTimer.singleShot(0, self.firstTabReady.emit)

        self.stack.addWidget(term)          # stack index == tab index (no reorder)
        idx = self.tabbar.addTab(name)
        self.tabbar.setCurrentIndex(idx)
        self.stack.setCurrentIndex(idx)
        self._update_add_controls()

    def _update_add_controls(self) -> None:
        at_cap = self.tabbar.count() >= _MAX_TABS
        self.add_btn.setEnabled(not at_cap)
        self.menu_btn.setEnabled(not at_cap)
        tip = f"Max {_MAX_TABS} terminal tabs open at once" if at_cap else self._profiles[0][0]
        self.add_btn.setToolTip(tip)
        self.menu_btn.setToolTip(tip if at_cap else "New terminal by profile")

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
        self._update_add_controls()

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
        /* Square-cornered blocks everywhere -- no rounded pill tabs on any
        terminal page (Wizard Console included). Fixed-mode pages
        (`blockStyle="true"`) additionally stretch tabs to fill the full
        width evenly; Wizard's content-sized, closable, reorderable tabs
        keep that behavior, just with the same square chrome. */
        QTabBar#TermTabBar {{ background: {CONSOLE_BG}; }}
        QTabBar#TermTabBar::tab {{
            background: {PANEL};
            color: {TERM_MUTE};
            padding: 6px 14px;
            margin: 0;
            border: none;
            border-right: 1px solid {BORDER_SOFT};
            border-radius: 0;
        }}
        QTabBar#TermTabBar::tab:hover {{
            background: {PANEL_LIGHT};
            color: {CONSOLE_TEXT};
        }}
        QTabBar#TermTabBar::tab:selected {{
            background: {CONSOLE_BG};
            color: {CONSOLE_TEXT};
            border-right: 1px solid {BORDER_SOFT};
            border-bottom: 3px solid {_TAB_ACCENT};
        }}
        /* Fixed/"block" tabs (today: LLM Mode's "LLM Nmap"/"OpenCode" pair)
        get the app's own purple accent instead of the orange used by
        Wizard Console/Raw Output's tabs, so they read as part of the same
        page as the gated panel beside them rather than a mismatched color
        borrowed from elsewhere in the app. */
        QTabBar#TermTabBar[blockStyle="true"]::tab {{
            font-size: 14px;
            font-weight: 600;
            padding: 10px 14px;
        }}
        QTabBar#TermTabBar[blockStyle="true"]::tab:hover {{
            background: {PANEL_LIGHT};
            color: {CONSOLE_TEXT};
        }}
        QTabBar#TermTabBar[blockStyle="true"]::tab:selected {{
            background: {CONSOLE_BG};
            color: {CONSOLE_TEXT};
            border-right: 1px solid {BORDER_SOFT};
            border-bottom: 3px solid {PURPLE};
        }}
        QToolButton#TermTabBtn {{
            color: {TERM_MUTE};
            font-size: 16px;
            font-weight: 700;
            border: none;
            border-radius: 0;
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
