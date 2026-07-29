"""
Terminal display helpers — banners, sections, status lines, impact boxes.

Color helpers (bold/cyan/green/red/yellow/magenta/blue) are re-exported from
`core.color` so callers can keep importing everything from `core.display`.
"""

import textwrap

from core.color import (
    red, green, yellow, blue, magenta, cyan, bold,
)

__all__ = [
    "banner", "section", "info", "ok", "warn", "fail", "impact_box",
    "red", "green", "yellow", "blue", "magenta", "cyan", "bold",
]

_WIDTH = 56


def banner(title: str, subtitle: str = "") -> None:
    """Print the top-of-program banner (matches bash.md layout)."""
    bar = "═" * _WIDTH
    print(f"\n{cyan(bar)}")
    print(f"  {bold(title)}")
    if subtitle:
        print(f"  {subtitle}")
    print(f"{cyan(bar)}\n")


def section(text: str) -> None:
    """Print a titled section divider."""
    label = f" {text} "
    dashes = "─" * max(0, _WIDTH - len(label))
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
    inner = _WIDTH
    top = "┌─ IMPACT " + "─" * max(0, inner - 9)
    bottom = "└" + "─" * inner
    print(f"  {yellow(top)}")
    for line in textwrap.wrap(text, inner - 2) or [""]:
        print(f"  {yellow('│')} {line}")
    print(f"  {yellow(bottom)}")
