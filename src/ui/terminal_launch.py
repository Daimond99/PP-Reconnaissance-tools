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

# What OpenCode's own shell tool is allowed to invoke by bare name, once
# PATH is restricted to `~/.recon_agent_bin` — the 6 authorized tools plus
# a handful of read-only utilities it needs to be minimally useful (reading
# scan output, loot files). Nothing that installs packages or reaches the
# network on its own (no git/curl/python/ssh/apt).
_SCOPE_TOOLS = ["nmap", "masscan", "hydra", "ncrack", "ncat", "evil-winrm"]
_SCOPE_UTILS = ["ls", "cat", "grep", "find", "head", "tail", "wc", "file", "mkdir", "touch"]

# nmap/masscan need the container's own scoped-sudo (docker/Dockerfile's
# NOPASSWD rule for exactly those two binaries) -- baked into the wrapper
# itself so a caller (human or OpenCode) never has to type "sudo".
_SUDO_IN_CONTAINER = {"nmap", "masscan"}
_TOOL_CONTAINER = "therecon-tools"


def _wrapper_lines(dir_expr: str, tool: str, interactive_tty: bool) -> list[str]:
    """The two bash lines that (re)write one `docker exec`-into-the-container
    wrapper script for `tool` into `dir_expr` (a shell expression for the
    target directory, e.g. `"$SCOPE_BIN"` or `"$HOME/.recon_docker_bin"`).
    Shared by `_tool_wrapper_snippet` (plain Shell/LLM tabs) and
    `_opencode_launch` (its own `$SCOPE_BIN`) so both PATH-scoping schemes
    point at the same container instead of the real host binary. nmap/
    masscan wrappers run `sudo` *inside* the container (its own
    NOPASSWD-scoped sudoers rule, docker/Dockerfile) so callers never need
    to type sudo themselves."""
    flag = "-it" if interactive_tty else "-i"
    inner = f"sudo {tool}" if tool in _SUDO_IN_CONTAINER else tool
    # `dir_expr` already carries its own quoting (e.g. `"$SCOPE_BIN"`) --
    # adjacent quoted/unquoted concatenation (`"$SCOPE_BIN"/nmap`) is valid
    # bash, so `path` must NOT be wrapped in another layer of quotes below.
    path = f'{dir_expr}/{tool}'
    return [
        f"printf '#!/bin/bash\\nexec docker exec {flag} "
        f"{_TOOL_CONTAINER} {inner} \"$@\"\\n' > {path};",
        f'chmod +x {path};',
    ]


def _tool_wrapper_snippet(interactive_tty: bool) -> str:
    """Bash fragment: (re)generate one wrapper script per authorized tool
    in `~/.recon_docker_bin`, each `docker exec`-ing the same-named binary
    inside the `therecon-tools` container (docker/Dockerfile) instead of
    reaching whatever copy is installed directly on this WSL host. The
    host still has its own copies (the pre-container "Windows Demo"
    install) -- this PATH-scoping is what actually stops a tab from
    reaching those directly instead of the sandboxed ones. See
    docs/List การเเก้ไข.md item 5 / docker/run.sh for the container itself.

    `interactive_tty=True` adds `-t` (real terminal, arrow keys, etc. --
    for a human typing into an actual pty, e.g. the plain Shell tab).
    `interactive_tty=False` uses `-i` only: OpenCode's own bash tool may
    not hand its child a real controlling tty, and `docker exec -t`
    without one fails outright ("the input device is not a TTY")."""
    lines = [
        'if [ -n "$HOME" ]; then',
        '  mkdir -p "$HOME/.recon_docker_bin";',
    ]
    for t in _SCOPE_TOOLS:
        for line in _wrapper_lines('"$HOME/.recon_docker_bin"', t, interactive_tty):
            lines.append(f"  {line}")
    lines.append('  export PATH="$HOME/.recon_docker_bin:$PATH";')
    lines.append("fi; ")
    return "\n".join(lines) + " "

_AGENTS_MD = (
    "# Scope\n\n"
    "This OpenCode session works with TheRecon's 6 authorized tools:\n"
    "nmap, masscan, hydra, ncrack, ncat, evil-winrm. Targets are limited to\n"
    "the user's own authorized lab scope -- never suggest or run against a\n"
    "target the user hasn't named in this session.\n\n"
    "## Allowed without asking\n\n"
    "- Read-only recon: nmap discovery/version/script scans (-sV, -sC, -A),\n"
    "  listing/viewing existing scan output or loot files.\n"
    "- A single, low-rate ncat connectivity check.\n\n"
    "## Ask first, wait for an explicit yes\n\n"
    "- Any hydra or ncrack run (brute force / credential guessing).\n"
    "- Any evil-winrm session (post-exploitation, remote code execution).\n"
    "- Aggressive/high-rate scans (masscan, nmap -T4/-T5, full -p-).\n"
    "- Anything against a target not already confirmed in-scope this "
    "session.\n\n"
    "When unsure, ask a clarifying question or propose the command instead\n"
    "of running it.\n\n"
    "## Advanced usage reference\n\n"
    "Use each tool's full capability -- the Ask-first list above is the only\n"
    "restriction, not the flags below.\n\n"
    "- nmap: `-sC -sV` default recon; `-p- --min-rate=1000 -T4` fast full-port\n"
    "  sweep; `-A` aggressive (OS + version + default scripts + traceroute,\n"
    "  noisy); `--script vuln` vulnerability scan; `--script=smb-*` /\n"
    "  `http-*` for protocol-targeted NSE.\n"
    "- masscan: `-p<ports> <target> --rate=<n>` for a fast internet-scale\n"
    "  port sweep, then hand live ports to nmap `-sV` for service detail.\n"
    "- hydra: `-f -t 16 -l <user> -P <wordlist> <service>://<target>`\n"
    "  (stop on first hit); `-L <userlist>` instead of `-l` for multiple\n"
    "  usernames.\n"
    "- ncrack: `-U <users.txt> -P <pass.txt> <service>://<target>`, same\n"
    "  idea as hydra with its own timing/retry controls.\n"
    "- ncat: `-l -p <port> -e /bin/bash -i` for a listener/shell, `--ssl`\n"
    "  to wrap the channel in TLS.\n"
    "- evil-winrm: `-i <target> -u <user> -p <pass>` for an interactive\n"
    "  WinRM shell; `-e <path>` to load local executables into the session.\n"
)

# Technical backstop for the "ask first" section above -- AGENTS.md is only
# a prompt (the model can ignore it), so the actual approval gate is
# OpenCode's own `permission.bash` config (opencode.json, project root =
# the workspace dir). Default "allow" so nmap/masscan/ncat run at full
# power with no extra prompting; only the tools/flags that need a human
# in the loop are downgraded to "ask". Last matching pattern wins, so the
# risky rules are listed after the "*" default.
_OPENCODE_JSON = (
    "{\n"
    '  "$schema": "https://opencode.ai/config.json",\n'
    '  "permission": {\n'
    '    "bash": {\n'
    '      "*": "allow",\n'
    '      "hydra *": "ask",\n'
    '      "ncrack *": "ask",\n'
    '      "evil-winrm*": "ask",\n'
    '      "masscan *": "ask",\n'
    '      "*-T4*": "ask",\n'
    '      "*-T5*": "ask",\n'
    '      "*-p-*": "ask"\n'
    "    }\n"
    "  }\n"
    "}\n"
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
        f"{_tool_wrapper_snippet(interactive_tty=True)}"
        "exec bash -l"
    )


def _llm_launch(llm_dir: str) -> str:
    """cd into the llm-tools-nmap plugin dir (and lock the shell to it, see
    `_confine_snippet`), and if `llm` has no stored API key yet, offer to
    set one right there before dropping into the shell — `llm keys list`
    prints the literal string "No keys found" when empty."""
    return (
        _confine_snippet(llm_dir) +
        f"{_tool_wrapper_snippet(interactive_tty=False)}"
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
    the intended scope and an opencode.json permission config (only if they
    don't already exist there — the user may edit either), then rebuild a
    restricted PATH (`~/.recon_agent_bin`, symlinks to only the 6 authorized
    tools + a few read-only utilities) before launching OpenCode. AGENTS.md
    is just a prompt (the model can ignore it); opencode.json's
    `permission.bash` rules are the real, tool-enforced gate that makes
    OpenCode actually stop and ask before hydra/ncrack/evil-winrm or an
    aggressive scan — everything else stays "allow" so the 6 tools run at
    full power with no extra prompting. PATH-scoping restricts what
    OpenCode's shell tool can invoke *by bare name* — it is not a hard
    sandbox, an absolute path still reaches anything on the real
    filesystem, but it blocks the common case of it reaching for
    git/curl/python/apt on its own."""
    utils = " ".join(_SCOPE_UTILS)
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
        f"if [ ! -f opencode.json ]; then cat > opencode.json << 'OCJSONEOF'\n"
        f"{_OPENCODE_JSON}OCJSONEOF\n"
        "fi; "
        # Installed for consistency with every other tab, but it's inert
        # here in practice: PROMPT_COMMAND only fires at an interactive
        # bash prompt, and this tab never reaches one -- it loops straight
        # into OpenCode itself (see the respawn loop below). PATH-scoping
        # (below) is the only real control this tab has over where
        # OpenCode's own shell tool can reach.
        f"{_confine_snippet(workspace_dir, do_cd=False)}"
        'SCOPE_BIN="$HOME/.recon_agent_bin"; mkdir -p "$SCOPE_BIN"; '
        # Delete only entries this script itself would have created, one
        # named path at a time -- never a `dir/*` glob, which silently
        # becomes a root-level glob if `$SCOPE_BIN` were ever empty.
        f'for t in {utils}; do rm -f "$SCOPE_BIN/$t"; done; '
        f'for t in {utils}; do p=$(command -v "$t" 2>/dev/null); '
        '[ -n "$p" ] && ln -sf "$p" "$SCOPE_BIN/$t"; done; '
        # The 6 authorized tools are wrapper scripts into the sandboxed
        # container instead of symlinks to the real host binary -- this is
        # the actual fix for the scenario a target's own malicious banner
        # (indirect prompt injection) tricks OpenCode into running a
        # dangerous suggested command: it still only ever reaches the
        # container copy, never the real WSL2 host tool.
        + "".join(
            f'{line} '
            for t in _SCOPE_TOOLS
            for line in _wrapper_lines('"$SCOPE_BIN"', t, interactive_tty=False)
        ) +
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
