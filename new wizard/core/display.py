"""
Terminal display helpers — banners, sections, status lines, impact boxes.

Color helpers (bold/cyan/green/red/yellow/magenta/blue) are re-exported from
`core.color` so callers can keep importing everything from `core.display`.
"""

import shutil
import textwrap

from core.color import (
    red, green, yellow, blue, magenta, cyan, bold,
)

__all__ = [
    "banner", "section", "info", "ok", "warn", "fail", "impact_box",
    "red", "green", "yellow", "blue", "magenta", "cyan", "bold",
]

_MAX_WIDTH = 56


def _width() -> int:
    """Bar/box width, adapted to the real terminal so it never wraps.

    In a PTY (e.g. the GUI Wizard Console) this reflects the pane's actual
    column count, so banners and dividers shrink to fit a narrow pane instead
    of wrapping onto a second line. Capped at _MAX_WIDTH for readability."""
    try:
        cols = shutil.get_terminal_size((80, 24)).columns
    except Exception:
        cols = 80
    return max(20, min(_MAX_WIDTH, cols - 2))


def banner(title: str, subtitle: str = "") -> None:
    """Print the top-of-program banner (matches bash.md layout)."""
    width = _width()
    bar = "═" * width
    print(f"\n{cyan(bar)}")
    print(f"  {bold(title)}")
    if subtitle:
        print(f"  {subtitle}")
    print(f"{cyan(bar)}\n")


def section(text: str) -> None:
    """Print a titled section divider."""
    label = f" {text} "
    dashes = "─" * max(0, _width() - len(label))
    print(f"\n{cyan('───' + label + dashes)}")


def info(text: str) -> None:
    print(f"  {blue('[*]')} {text}")


def ok(text: str) -> None:
    print(f"  {green('[+]')} {text}")


def warn(text: str) -> None:
    print(f"  {yellow('[!]')} {text}")


def fail(text: str) -> None:
    print(f"  {red('[-]')} {text}")


def impact_box(text: str) -> None:
    """Render a boxed impact/warning note under a step."""
    inner = _width()
    top = "┌─ IMPACT " + "─" * max(0, inner - 9)
    bottom = "└" + "─" * inner
    print(f"  {yellow(top)}")
    for line in textwrap.wrap(text, inner - 2) or [""]:
        print(f"  {yellow('│')} {line}")
    print(f"  {yellow(bottom)}")
