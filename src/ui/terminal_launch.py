"""Launch-script + path builders for the terminal backends.

Pure string/path logic, no Qt — split out of `terminal_tabs.py` (2026-08-07)
so the bash launch scripts and the Windows→WSL path derivation can be unit
tested on their own. `terminal_tabs.make_terminal()` composes these into the
actual `wsl.exe`/`bash` argv it hands to a terminal widget.

WSL-side paths are derived at runtime from wherever this repo actually lives
on THIS machine (see `_wsl_root_dir()`), never hardcoded to the original dev
machine's `D:\\TheRecon`, which would break on any other clone location.
"""

from __future__ import annotations

import os
import shlex

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


# -- on-disk / WSL path derivation ------------------------------------------

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


def _win_to_wsl_path(win_path: str) -> str:
    """Convert an absolute Windows path (`D:\\TheRecon`) to its WSL
    mount-point form (`/mnt/d/TheRecon`) -- same drive-letter-to-/mnt/x
    mapping `validation.common.convert_windows_paths_to_wsl` uses for
    user-supplied command paths, applied here once to the repo's own
    on-disk location instead of scanning a whole command string."""
    drive, rest = os.path.splitdrive(os.path.abspath(win_path))
    return f"/mnt/{drive.rstrip(':').lower()}/{rest.replace(chr(92), '/').lstrip('/')}"


def _wsl_root_dir() -> str:
    """Repo root as seen from inside WSL -- wherever this repo actually
    lives on THIS machine, not the original dev machine's `D:\\TheRecon`."""
    return _win_to_wsl_path(_repo_root_dir())


def _wsl_dir() -> str:
    return f"{_wsl_root_dir()}/chain_wizard"


def _wsl_llm_dir() -> str:
    return f"{_wsl_root_dir()}/tools/llm-tools-nmap"


def _wsl_opencode_dir() -> str:
    return f"{_wsl_root_dir()}/tools/opencode-workspace"


# -- bash launch-script fragments -------------------------------------------

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
    'if [ -n "$TR_SCOPE_DIR" ] && [ -d "$TR_SCOPE_DIR" ]; then\n'
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
        # Banner width is hardcoded, not read from `tput cols`/$COLUMNS --
        # querying real terminal size this early (before the pane's first
        # PTY-resize round-trip lands, see term.html's retry-fit loop) is
        # exactly the stale-size trap that caused the cursor/reflow bug this
        # banner was rewritten to avoid; every line here is kept comfortably
        # under 56 cols (chain_wizard/core/display.py's own _MAX_WIDTH) so
        # it can never wrap regardless of the pane's real width.
        "_bar='" + "=" * 54 + "'; "
        "printf '\\n\\033[36m%s\\033[0m\\n' \"$_bar\"; "
        "printf '  \\033[1mLLM Nmap\\033[0m\\n'; "
        "printf '  AI-assisted nmap scanning via the llm CLI\\n'; "
        "printf '\\033[36m%s\\033[0m\\n\\n' \"$_bar\"; "
        "printf '  \\033[34m[*]\\033[0m Example:\\n'; "
        "printf '  \\033[34m[*]\\033[0m llm --functions llm-tools-nmap.py "
        "\"scan TARGET\"\\n'; "
        "printf '  \\033[34m[*]\\033[0m -m <model>  ->  override the default "
        "model\\n'; "
        "printf '  \\033[34m[*]\\033[0m llm models -q gemini  ->  list gemini "
        "options\\n\\n'; "
        'if [ "$(llm keys list 2>/dev/null)" = "No keys found" ]; then '
        "printf '  \\033[33m[!]\\033[0m No LLM API key set yet.\\n'; "
        "printf '  \\033[33m[!]\\033[0m llm keys set openai  |  llm install "
        "llm-gemini && llm keys set gemini\\n'; "
        'printf "Set an OpenAI key now? [y/N] "; read ans; '
        'case "$ans" in y|Y|yes|Yes) llm keys set openai ;; esac; '
        "fi; "
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


def _wizard_arg_str(wizard_args: "list[str] | None") -> str:
    """POSIX-quote GUI-supplied wizard flags into a launch-command suffix.

    Returns e.g. ` --mode auto --target '192.168.1.1'` (leading space), or
    "" when no args — both WSL bash and native Linux bash are POSIX, so
    `shlex.quote` is the right escaper for either target."""
    if not wizard_args:
        return ""
    return " " + " ".join(shlex.quote(a) for a in wizard_args)
