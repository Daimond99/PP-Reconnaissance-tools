"""
Entry point — command-line interface for the chain wizard.
"""

import os
import sys
import glob
from core.display import banner, section, info, ok, warn, fail, bold, cyan, green, yellow
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
    raw = input(f"  {cyan(prompt)} [{default}]: ").strip()
    if not raw:
        return default

    # numeric pick from the detected menu
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(choices):
            return choices[idx]
        warn(f"No menu item #{raw} — treating '{raw}' as a path.")

    path = os.path.expanduser(raw)
    if not os.path.exists(path):
        warn(f"File not found: {path} — falling back to {default}")
        return default
    return path


def main() -> None:
    # Ensure box-drawing / ANSI output works on Windows consoles too
    # (WSL/Kali is already UTF-8). Safe no-op where unsupported.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    # Run the wizard in a loop so the pane is always "the wizard":
    #   Ctrl-C  → cancel the current step, restart at the mode menu.
    #   finish  → offer a fresh run (re-print the banner).
    #   Ctrl-D  → exit for real (the launcher drops to a shell as an escape).
    while True:
        try:
            _interactive()
        except KeyboardInterrupt:
            print(f"\n  {yellow('Cancelled — restarting the wizard.')}\n")
            continue
        except EOFError:
            print(f"\n  {yellow('Exiting wizard.')}")
            return


def _interactive() -> None:
    banner(
        title="PENTEST CHAIN WIZARD",
        subtitle="auto / semi · nmap masscan hydra ncrack ncat evil-winrm",
    )

    print(f"  {yellow('You are authorized — no further permission required.')}\n")

    # ─── Mode selection ─────────────────────────────────────────
    print("  Select mode:")
    print(f"    {green('1')}. {bold('AUTO')} — auto-pick best tool per port, confirm each")
    print(f"    {green('2')}. {bold('SEMI')} — show all options, pick per port")
    mode_choice = input(f"  {cyan('Choice [1/2]: ')}").strip()
    mode = "auto" if mode_choice == "1" else "semi"
    ok(f"Mode: {mode.upper()}")

    # ─── Target ─────────────────────────────────────────────────
    target = input(f"\n  {cyan('Target (IP / domain / CIDR): ')}").strip()
    if not target:
        fail("No target provided — back to the start.")
        return

    # ─── Wordlists ──────────────────────────────────────────────
    _enable_path_completion()
    default_wl = "/usr/share/wordlists/rockyou.txt"

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
    run_chain(target, user_wl, pass_wl, mode)


if __name__ == "__main__":
    main()