"""
Color and style constants for terminal output.
Centralized to enable future GUI theming.
"""

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    red: str = "\033[91m"
    green: str = "\033[92m"
    yellow: str = "\033[93m"
    blue: str = "\033[94m"
    magenta: str = "\033[95m"
    cyan: str = "\033[96m"
    reset: str = "\033[0m"
    bold: str = "\033[1m"


PALETTE = Palette()


def _use_color() -> bool:
    """
    Emit ANSI color only when it will actually render:
      - honor the NO_COLOR convention (any value disables color), and
      - require an interactive TTY (a real terminal), so that when the CLI is
        piped into a GUI widget (e.g. TheRecon's Wizard Console, which reads
        our stdout through a QProcess pipe, not a PTY) we output clean plain
        text instead of raw escape codes like `\\x1b[96m`.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


_COLOR = _use_color()


def _wrap(code: str, text: str) -> str:
    return f"{code}{text}{PALETTE.reset}" if _COLOR else text


# ─── Stateless terminal helpers ───────────────────────────────────


def red(text: str) -> str:
    return _wrap(PALETTE.red, text)


def green(text: str) -> str:
    return _wrap(PALETTE.green, text)


def yellow(text: str) -> str:
    return _wrap(PALETTE.yellow, text)


def blue(text: str) -> str:
    return _wrap(PALETTE.blue, text)


def magenta(text: str) -> str:
    return _wrap(PALETTE.magenta, text)


def cyan(text: str) -> str:
    return _wrap(PALETTE.cyan, text)


def bold(text: str) -> str:
    return _wrap(PALETTE.bold, text)