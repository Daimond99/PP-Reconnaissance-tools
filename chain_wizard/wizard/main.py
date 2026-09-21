"""
Entry point for the chain wizard.

Two ways to run it:
  - Standalone (`python3 -m wizard.main`): interactive terminal, prompts for
    target/wordlists via `CliUI`, loops so the terminal is always "the
    wizard" until Ctrl-D.
  - `--target ... --gui` (the Qt GUI's Wizard Console): the panel's choices
    come in as flags, `IpcUI` takes over every menu/confirmation as a JSON
    line-protocol on stdin/stdout (see `core/ui_driver.py`), and the process
    exits after that one run — the GUI starts a fresh process per scan.
"""

import builtins
import functools
import os
import re
import sys
import glob
import argparse
from dataclasses import dataclass
from core.display import banner, section, info, ok, warn, fail, bold, cyan, green, yellow
from core.ui_driver import get_ui, set_ui, IpcUI
from wizard.chain import run_chain

try:
    import readline  # enables TAB path-completion on the wordlist prompt
except ImportError:  # not available on some platforms (e.g. bare Windows)
    readline = None

# Directories scanned for ready-to-pick wordlists (first existing files win).
_WORDLIST_DIRS = [
    "/mnt/d/TheRecon",
    os.path.expanduser("~/wordlists"),
    os.path.expanduser("~"),
    "/usr/share/wordlists",
    "/usr/share/seclists/Passwords",
]


def _win_to_wsl_path(path: str) -> str:
    """Convert a Windows-style path (`C:\\...` / `C:/...`) to its WSL
    `/mnt/c/...` form. No-op for anything that isn't a drive-letter path
    (already-POSIX paths pass straight through). The wizard always executes
    inside WSL/Linux bash, which has no drive letters -- a raw Windows path
    (e.g. from the GUI's wordlist Browse... dialog, which runs on Windows
    Python) silently fails to resolve there otherwise."""
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", path)
    if not m:
        return path
    drive, rest = m.group(1).lower(), m.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def _enable_path_completion() -> None:
    """Turn on filesystem TAB-completion for input() prompts (best effort)."""
    if not readline:
        return

    def _complete(text: str, state: int):
        stub = os.path.expanduser(text)
        matches = glob.glob(stub + "*")
        matches = [m + ("/" if os.path.isdir(m) else "") for m in matches]
        return matches[state] if state < len(matches) else None

    readline.set_completer_delims(" \t\n")
    readline.set_completer(_complete)
    readline.parse_and_bind("tab: complete")


def _discover_wordlists() -> list[str]:
    """Return existing *.txt / *.lst wordlists found in the known dirs."""
    found: list[str] = []
    seen: set[str] = set()
    for d in _WORDLIST_DIRS:
        for pat in ("*.txt", "*.lst"):
            for p in sorted(glob.glob(os.path.join(d, pat))):
                if os.path.isfile(p) and p not in seen:
                    seen.add(p)
                    found.append(p)
    return found


def _resolve_wordlist(prompt: str, default: str, choices: list[str]) -> str:
    """
    Prompt for a wordlist. Accepts either:
      - a number from the detected-wordlists menu, or
      - a typed/pasted path (TAB-completes), or
      - blank to use `default`.
    Falls back to `default` if the chosen path doesn't exist.
    """
    raw = get_ui().text(prompt, default)
    if not raw:
        return default

    # numeric pick from the detected menu
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(choices):
            return choices[idx]
        warn(f"No menu item #{raw} — treating '{raw}' as a path.")

    path = _win_to_wsl_path(os.path.expanduser(raw))
    if not os.path.exists(path):
        warn(f"File not found: {path} — falling back to {default}")
        return default
    return path


@dataclass
class _Preset:
    """Choices supplied up front (by the GUI dialog) instead of prompted."""
    target: str
    user_wl: str
    pass_wl: str


def _parse_args(argv: list[str] | None = None) -> tuple[_Preset | None, bool]:
    """Parse the GUI's up-front flags. Returns (`_Preset` when `--target`
    is given, else `None` → fully interactive, unchanged behavior; whether
    `--gui` was passed)."""
    p = argparse.ArgumentParser(prog="wizard", add_help=True)
    p.add_argument("--target", help="IP / domain / CIDR to scan")
    p.add_argument("--user-wordlist", dest="user_wl", default="")
    p.add_argument("--pass-wordlist", dest="pass_wl", default="")
    p.add_argument("--gui", action="store_true",
                    help="Talk the JSON IPC protocol on stdin/stdout instead "
                         "of prompting a terminal — set by the Qt GUI launcher.")
    a = p.parse_args(argv)

    if not a.target:
        return None, a.gui

    default_wl = "/usr/share/wordlists/rockyou.txt"
    user_wl = _win_to_wsl_path(a.user_wl) or default_wl
    pass_wl = _win_to_wsl_path(a.pass_wl) or user_wl
    return _Preset(target=a.target, user_wl=user_wl, pass_wl=pass_wl), a.gui


def main() -> None:
    # Ensure box-drawing / ANSI output works on Windows consoles too
    # (WSL/Kali is already UTF-8). Safe no-op where unsupported.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    preset, use_gui = _parse_args()
    if use_gui:
        set_ui(IpcUI())
        # Reserve real stdout exclusively for the IpcUI JSON protocol — every
        # `print()` call in this package (banners, section dividers, status
        # lines via core/display.py, and the few bare `print()`s in
        # wizard/chain.py) would otherwise interleave raw text into the
        # stream the Qt side is parsing as JSON. Redirecting the builtin
        # once here, instead of touching every call site, keeps CliUI's
        # behavior (and every other module) byte-identical when --gui is
        # not set.
        builtins.print = functools.partial(print, file=sys.stderr)

    # Only the first pass honors the GUI-supplied preset; every run after
    # (the pane loops so it's always "the wizard") is fully interactive --
    # but `last` carries the most recently used target/wordlists
    # forward as the *defaults* for those prompts (Enter reuses them), so
    # a GUI-launched target doesn't get thrown away and re-typed from
    # scratch on every loop.
    last: "_Preset | None" = preset

    if use_gui:
        # One QProcess run == one "Start scan" click: the GUI already offers
        # a fresh form for the next scan, so there's no terminal to loop
        # back into here. Run the single preset pass and exit — no
        # KeyboardInterrupt/EOFError handling needed either, since there's
        # no real tty for Ctrl-C/Ctrl-D to arrive on.
        _interactive(preset, last)
        return

    # Run the wizard in a loop so the pane is always "the wizard":
    #   Ctrl-C  → cancel the current step, restart at the target prompt.
    #   finish  → offer a fresh run (re-print the banner).
    #   Ctrl-D  → exit for real (the launcher drops to a shell as an escape).
    while True:
        try:
            used = _interactive(preset, last)
            if used is not None:
                last = used
            preset = None  # subsequent runs prompt normally
        except KeyboardInterrupt:
            preset = None
            print(f"\n  {yellow('Cancelled — restarting the wizard.')}\n")
            continue
        except EOFError:
            print(f"\n  {yellow('Exiting wizard.')}")
            return


def _interactive(
    preset: "_Preset | None" = None,
    last: "_Preset | None" = None,
) -> "_Preset | None":
    """Run one wizard pass. Returns the `_Preset` actually used (so the
    caller can offer it back as next loop's defaults), or `None` if the
    user aborted before a target was chosen."""
    banner(
        title="PENTEST CHAIN WIZARD",
        subtitle="nmap masscan hydra ncrack ncat evil-winrm",
    )

    print(f"  {yellow('You are authorized — no further permission required.')}\n")

    # ─── Preset path (GUI dialog) — skip prompts, summarize, run ─
    if preset is not None:
        ok(f"Target: {preset.target}")
        ok(f"User wordlist: {preset.user_wl}")
        ok(f"Pass wordlist: {preset.pass_wl}")
        print()
        run_chain(preset.target, preset.user_wl, preset.pass_wl)
        return preset

    # ─── Target (defaults to the last-used target — blank reuses it) ─
    default_target = last.target if last else ""
    target = get_ui().text("Target (IP / domain / CIDR)", default_target)
    if not target:
        fail("No target provided — back to the start.")
        return None

    # ─── Wordlists ──────────────────────────────────────────────
    _enable_path_completion()
    default_wl = last.user_wl if last else "/usr/share/wordlists/rockyou.txt"

    found = _discover_wordlists()
    if found:
        section("DETECTED WORDLISTS")
        for i, p in enumerate(found, 1):
            print(f"    {green(str(i))}. {p}")
        info("Pick a number, or type/paste a path (press TAB to complete), or blank for default.")
    else:
        info("No wordlists auto-detected — type/paste a path (TAB completes), or blank for default.")

    user_wl = _resolve_wordlist("User wordlist", default_wl, found)
    pass_wl = _resolve_wordlist("Pass wordlist (leave blank for same)", user_wl, found)

    # ─── Execute ────────────────────────────────────────────────
    run_chain(target, user_wl, pass_wl)
    return _Preset(target=target, user_wl=user_wl, pass_wl=pass_wl)


if __name__ == "__main__":
    main()