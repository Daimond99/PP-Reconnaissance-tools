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
import shutil
import subprocess

from PySide6.QtCore import Qt, QTimer, Signal
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

# Each tab is a separate QWebEngineView = a separate Chromium renderer
# process (plus its own wsl.exe/bash PTY) — capping how many can be open at
# once keeps the app usable on lower-spec machines instead of letting the
# user pile up processes until the machine chokes.
_MAX_TABS = 4

_WSL_DIR = "/mnt/d/TheRecon/chain_wizard"
_WSL_LLM_DIR = "/mnt/d/TheRecon/tools/llm-tools-nmap"
_WSL_OPENCODE_DIR = "/mnt/d/TheRecon/tools/opencode-workspace"
# Repo root — the "own path" a plain Shell tab is confined to (see
# _confine_snippet); wider than the other tabs' single-purpose dirs since
# Shell is meant to be usable across the whole project, not just one tool.
_WSL_ROOT_DIR = "/mnt/d/TheRecon"

# What OpenCode's own shell tool is allowed to invoke by bare name, once
# PATH is restricted to `~/.recon_agent_bin` — the 6 authorized tools plus
# a handful of read-only utilities it needs to be minimally useful (reading
# scan output, loot files). Nothing that installs packages or reaches the
# network on its own (no git/curl/python/ssh/apt).
_SCOPE_TOOLS = ["nmap", "masscan", "hydra", "ncrack", "ncat", "evil-winrm"]
_SCOPE_UTILS = ["ls", "cat", "grep", "find", "head", "tail", "wc", "file", "mkdir", "touch"]

_AGENTS_MD = (
    "# Scope\n\n"
    "This OpenCode session is restricted to TheRecon's 6 authorized tools:\n"
    "nmap, masscan, hydra, ncrack, ncat, evil-winrm.\n\n"
    "Only those 6 tools plus a few read-only utilities (ls, cat, grep, find,\n"
    "head, tail, wc, file, mkdir, touch) are on PATH in this shell -- \n"
    "everything else (git, python, curl, pip, apt, ssh, ...) is\n"
    "intentionally unavailable. Do not attempt package installs or try to\n"
    "reach outside this scope.\n"
)

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


def _repo_root_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _repo_local_dir() -> str:
    return os.path.join(_repo_root_dir(), "chain_wizard")


def _repo_local_llm_dir() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(repo_root, "tools", "llm-tools-nmap")


def _repo_local_opencode_dir() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(repo_root, "tools", "opencode-workspace")


def _bashrc_once(marker: str, body: str) -> str:
    """Bash fragment: append `body` to `~/.bashrc` once, guarded by
    `marker` so re-opening the tab doesn't keep re-appending it. Caller
    must have already verified `$HOME` is non-empty. `body` is written via
    a quoted heredoc (`'RCEOF'`), so it lands in the file completely
    literally -- no `$VAR`/backtick expansion happens at append time, only
    later when `~/.bashrc` itself is sourced."""
    return (
        f"if ! grep -qF '{marker}' \"$HOME/.bashrc\" 2>/dev/null; then "
        f"cat >> \"$HOME/.bashrc\" << 'RCEOF'\n"
        f"{marker}\n{body}"
        "RCEOF\n"
        "fi; "
    )


_CONFINE_MARKER = "# TheRecon: confine cd to this tab scope dir (auto-added)"
_CONFINE_BODY = (
    'if [ -n "$TR_SCOPE_DIR" ]; then\n'
    "  _tr_confine() {\n"
    '    case "$PWD" in\n'
    '      "$TR_SCOPE_DIR"|"$TR_SCOPE_DIR"/*) ;;\n'
    "      *) echo \"[!] left this tab's allowed path -- back to "
    '$TR_SCOPE_DIR" >&2; cd "$TR_SCOPE_DIR" 2>/dev/null || cd "$HOME";;\n'
    "    esac\n"
    "  }\n"
    '  case ";$PROMPT_COMMAND;" in\n'
    '    *";_tr_confine;"*) ;;\n'
    '    *) PROMPT_COMMAND="_tr_confine${PROMPT_COMMAND:+; $PROMPT_COMMAND}";;\n'
    "  esac\n"
    "fi\n"
)


def _confine_snippet(scope_dir: str, do_cd: bool = True) -> str:
    """`$HOME`-guarded bash fragment that locks the interactive shell to
    `scope_dir`: installs (once, via `~/.bashrc`) a `PROMPT_COMMAND` hook
    that snaps `$PWD` back to `$TR_SCOPE_DIR` after every command if it
    ever ends up outside it. Checking `$PWD` after the fact, rather than
    trying to intercept `cd` itself, is what makes this catch every way of
    moving the shell's directory (`cd`, `pushd`, a sourced script that
    `cd`s) instead of just a literal `cd ..` typed at the prompt.

    Only takes effect once bash reaches an *interactive* prompt --
    `PROMPT_COMMAND` is a no-op in a non-interactive/scripted shell, so
    this doesn't do anything for the OpenCode tab, which never drops to a
    bash prompt at all (see `_opencode_launch`'s respawn loop); OpenCode's
    own PATH-scoping is the only control that tab has today.

    `do_cd=False` skips the initial `cd` when the caller still needs to
    `mkdir`/set up `scope_dir` itself first."""
    cd_part = f"cd '{scope_dir}' 2>/dev/null; " if do_cd else ""
    return (
        'if [ -z "$HOME" ]; then '
        'echo "[!] \\$HOME is not set -- skipping path confinement."; '
        "else "
        f"{_bashrc_once(_CONFINE_MARKER, _CONFINE_BODY)}"
        f'export TR_SCOPE_DIR="{scope_dir}"; '
        "fi; "
        f"{cd_part}"
    )


_OPENCODE_BLOCK_MARKER = "# TheRecon: block opencode in this shell (auto-added)"
_OPENCODE_BLOCK_BODY = (
    'if [ -n "$TR_BLOCK_OPENCODE" ]; then\n'
    "  shopt -s extdebug\n"
    "  trap 'case \"$BASH_COMMAND\" in *opencode*) "
    'echo "[!] opencode is blocked in this shell -- use the OpenCode tab '
    "in LLM Mode instead.\" >&2; false;; esac' DEBUG\n"
    "fi\n"
)


def _shell_launch(scope_dir: str) -> str:
    """Plain interactive shell (Wizard Console's "+" Shell tab, and Raw
    Output's backend), with `opencode` blocked from being run out of it --
    the OpenCode agent is only meant to be reached through its own scoped
    tab in LLM Mode (restricted PATH, dedicated workspace), not launched
    ad hoc from a general-purpose shell.

    A plain `trap ... DEBUG` can't actually stop a command from running --
    it only *observes* the next simple command, its exit status doesn't
    cancel anything. `shopt -s extdebug` changes that: a DEBUG trap that
    returns non-zero then causes bash to skip the next command entirely
    instead of running it (documented bash behavior, the same primitive
    shell debuggers use to single-step/skip). Matches "opencode" as a
    plain substring of the about-to-run command line, so it catches the
    bare command, a full/relative path to the same binary, and it being
    wrapped in `bash -c "..."`, `sh -c "..."`, etc. -- not just a bare-name
    PATH lookup the way an alias/function override or PATH-scoping would
    only cover.

    Installed via `~/.bashrc` (guarded by `TR_BLOCK_OPENCODE`, only set by
    this launch path) rather than inline, because the trap has to be set
    inside the *actual* interactive shell the user types into --
    `exec bash -l` replaces the process image, and traps set beforehand
    don't survive that; only exported environment variables do.

    Also locks the shell to `scope_dir` (see `_confine_snippet`) so it
    can't `cd` its way out to the rest of the filesystem either."""
    return (
        _confine_snippet(scope_dir) +
        'if [ -z "$HOME" ]; then '
        'echo "[!] \\$HOME is not set -- skipping opencode-block setup."; '
        "else "
        f"{_bashrc_once(_OPENCODE_BLOCK_MARKER, _OPENCODE_BLOCK_BODY)}"
        'export TR_BLOCK_OPENCODE=1; '
        "fi; "
        "exec bash -l"
    )


def _llm_launch(llm_dir: str) -> str:
    """cd into the llm-tools-nmap plugin dir (and lock the shell to it, see
    `_confine_snippet`), and if `llm` has no stored API key yet, offer to
    set one right there before dropping into the shell — `llm keys list`
    prints the literal string "No keys found" when empty."""
    return (
        _confine_snippet(llm_dir) +
        'if [ "$(llm keys list 2>/dev/null)" = "No keys found" ]; then '
        "echo '[!] No LLM API key set yet.'; "
        "echo 'Providers: llm keys set openai | llm install llm-gemini && llm keys set gemini'; "
        'printf "Set an OpenAI key now? [y/N] "; read ans; '
        'case "$ans" in y|Y|yes|Yes) llm keys set openai ;; esac; '
        "fi; "
        "echo '--- LLM Nmap ---'; "
        "echo 'Example:'; "
        "echo '  llm --functions llm-tools-nmap.py \"scan 192.168.1.1 for common ports\"'; "
        "echo '(add -m <model> to override the default model; llm models -q gemini lists gemini options)'; "
        "echo '----------------'; "
        "exec bash -l"
    )


def _opencode_launch(workspace_dir: str) -> str:
    """cd into a dedicated OpenCode workspace, drop an AGENTS.md describing
    the intended scope (only if one doesn't already exist there — the user
    may edit it), then rebuild a restricted PATH (`~/.recon_agent_bin`,
    symlinks to only the 6 authorized tools + a few read-only utilities)
    before launching OpenCode. This restricts what OpenCode's own shell
    tool can invoke *by bare name* — it is not a hard sandbox, an absolute
    path still reaches anything on the real filesystem, but it blocks the
    common case of it reaching for git/curl/python/apt on its own."""
    tools = " ".join(_SCOPE_TOOLS + _SCOPE_UTILS)
    return (
        # `$HOME` has been observed empty in some non-interactive WSL
        # invocation shapes -- abort before touching the filesystem at all
        # rather than let a `$HOME`-based path silently collapse to "" and
        # have a later cleanup step act on the wrong directory.
        'if [ -z "$HOME" ]; then '
        'echo "[!] \\$HOME is not set -- refusing to set up the OpenCode scope."; '
        'exec bash -l; '
        'fi; '
        # The official installer (curl -fsSL https://opencode.ai/install |
        # bash) only adds $HOME/.opencode/bin to PATH via ~/.bashrc, which
        # a non-interactive `bash -lc` launch (this one) never sources --
        # fall back to its known install path if a plain PATH lookup misses.
        # Resolved *before* PATH gets restricted below, and before that
        # restriction happens at all if opencode turns out to be missing --
        # otherwise the "not installed" fallback shell would itself be
        # unable to find `bash`.
        'OC=$(command -v opencode 2>/dev/null); '
        '[ -z "$OC" ] && [ -x "$HOME/.opencode/bin/opencode" ] && OC="$HOME/.opencode/bin/opencode"; '
        'if [ -z "$OC" ]; then '
        'echo "[!] opencode not installed. Install: curl -fsSL https://opencode.ai/install | bash"; '
        'exec bash -l; '
        'fi; '
        f"mkdir -p '{workspace_dir}' && cd '{workspace_dir}' && "
        f"if [ ! -f AGENTS.md ]; then cat > AGENTS.md << 'AGENTSEOF'\n"
        f"{_AGENTS_MD}AGENTSEOF\n"
        "fi; "
        # Installed for consistency with every other tab, but it's inert
        # here in practice: PROMPT_COMMAND only fires at an interactive
        # bash prompt, and this tab never reaches one -- it loops straight
        # into OpenCode itself (see the respawn loop below). PATH-scoping
        # (below) is the only real control this tab has over where
        # OpenCode's own shell tool can reach.
        f"{_confine_snippet(workspace_dir, do_cd=False)}"
        'SCOPE_BIN="$HOME/.recon_agent_bin"; mkdir -p "$SCOPE_BIN"; '
        # Delete only symlinks this script itself would have created, one
        # named path at a time -- never a `dir/*` glob, which silently
        # becomes a root-level glob if `$SCOPE_BIN` were ever empty.
        f'for t in {tools}; do rm -f "$SCOPE_BIN/$t"; done; '
        f'for t in {tools}; do p=$(command -v "$t" 2>/dev/null); '
        '[ -n "$p" ] && ln -sf "$p" "$SCOPE_BIN/$t"; done; '
        'export PATH="$SCOPE_BIN"; '
        # `exec bash -l` used to run here on exit, but PATH is scoped to
        # `$SCOPE_BIN` by this point, which never includes `bash` itself --
        # a bare-name lookup for it errored with "exec: bash: not found"
        # and killed the tab. Loop straight back into a fresh OpenCode
        # session on exit instead (per user request): never runs `exec
        # bash` once PATH is scoped, so that lookup never happens.
        # Ctrl+Z is dropped further upstream, in the Qt terminal widget
        # itself (`XtermTerminal._on_key`, `block_ctrl_z=True` for this
        # profile) -- OpenCode runs its TUI in raw mode, so the keystroke
        # never becomes a real SIGTSTP at the kernel level; it's OpenCode's
        # *own* handling of the raw 0x1A byte that was leaving the pane
        # blank, so `trap TSTP` here couldn't help (bash never saw it).
        # `sleep 1` guards against a tight crash-loop if `$OC` starts
        # failing instantly every run.
        'while :; do "$OC"; sleep 1; done'
    )


def make_terminal(profile: str, read_only: bool = False) -> QWidget:
    """Build a terminal widget for `profile` ("wizard" | "shell" |
    "llm-nmap" | "opencode").

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

    local_dir = _repo_local_dir()

    if profile == "wizard":
        # Confined *after* the wizard CLI itself runs, not before — the CLI
        # needs to run unconfined (it's the trusted, gated path), this only
        # locks the plain `bash -l` the script drops to once the CLI exits.
        wsl_launch = f"cd '{_WSL_DIR}' && python3 -m wizard.main; {_shell_launch(_WSL_DIR)}"
        lin_launch = f"cd '{local_dir}' && python3 -m wizard.main; {_shell_launch(local_dir)}"
    elif profile == "llm-nmap":
        wsl_launch = _llm_launch(_WSL_LLM_DIR)
        lin_launch = _llm_launch(_repo_local_llm_dir())
    elif profile == "opencode":
        wsl_launch = _opencode_launch(_WSL_OPENCODE_DIR)
        lin_launch = _opencode_launch(_repo_local_opencode_dir())
    else:  # plain interactive shell — opencode blocked, see _shell_launch()
        wsl_launch = _shell_launch(_WSL_ROOT_DIR)
        lin_launch = _shell_launch(_repo_root_dir())

    _SIMPLE_PROFILES = ("shell", "llm-nmap", "opencode")

    # 1. xterm.js web terminal — preferred, cross-platform.
    if XTERM_AVAILABLE:
        if os.name == "nt":
            # `-e` (--exec) matters, not just style: without it, wsl.exe
            # re-parses "bash -lc <script>" through an extra shell layer
            # that silently breaks multi-statement scripts — variable
            # assignments stop persisting across `;`-separated commands
            # (confirmed: `OC=x; [ -z "$OC" ] && echo BUG` prints BUG
            # without `-e`, correctly doesn't with it). Harmless for the
            # simple one-liner "wizard"/"shell" launches, but silently
            # broke "llm-nmap"/"opencode"'s multi-step setup scripts.
            argv = ["wsl.exe", "-e", "bash", "-lc", wsl_launch]  # default distro
        else:
            argv = ["bash", "-lc", lin_launch]
        return XtermTerminal(argv, block_ctrl_z=(profile == "opencode"), read_only=read_only)

    # 2. pyte ConPTY terminal — Windows-only legacy fallback.
    if PTY_AVAILABLE and os.name == "nt":
        return PtyTerminal(["wsl.exe", "-e", "bash", "-lc", wsl_launch], read_only=read_only)

    # 3. plain-pipe fallback — no TTY.
    if os.name == "nt":
        inner = wsl_launch if profile in _SIMPLE_PROFILES else \
            f"cd '{_WSL_DIR}' && python3 -m wizard.main"
        return InteractiveTerminal("wsl.exe", ["-e", "bash", "-lc", inner])
    inner = lin_launch if profile in _SIMPLE_PROFILES else \
        f"cd '{local_dir}' && python3 -m wizard.main"
    return InteractiveTerminal("bash", ["-lc", inner])


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
    # button's target and the always-open first tab. Wizard Console's
    # original two-profile set — other pages (e.g. the LLM/Agent page) pass
    # their own list.
    _DEFAULT_PROFILES = [
        ("New Wizard tab", "wizard", "Wizard"),
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
            # first tab always uses the first profile (Wizard by default;
            # whatever the caller passed first for other pages)
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
        QTabBar#TermTabBar[blockStyle="true"]::tab {{
            font-size: 14px;
            font-weight: 600;
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
