"""
UI backend abstraction — every interactive point in the wizard (menus,
free-text prompts, multi-select pickers, impact confirmations, the sudo
password) goes through this instead of calling `input()`/`print()` directly.

Two backends:
  - CliUI — the original terminal behavior, byte-for-byte (still used when
    `python3 -m wizard.main` is run standalone/headlessly for debugging).
  - IpcUI — used when the GUI launches the wizard (`--gui`). Every request
    becomes one JSON object written to real stdout, and blocks reading one
    JSON object back from stdin. stdout is reserved *exclusively* for this
    protocol in that mode — see `wizard/main.py`'s `--gui` startup, which
    redirects `print()` (and therefore every `core.display` helper) to
    stderr so decorative/log output never corrupts the JSON stream.

Selected once at process startup via `set_ui()`; every other module reaches
the active backend through `get_ui()` rather than importing a concrete class,
so swapping backends never touches call sites.
"""

from __future__ import annotations

import getpass
import json
import sys
import textwrap
from core.color import bold, cyan, green, magenta, yellow
from core.display import _width, info, section, warn


class UI:
    """Backend interface. See module docstring for the request shapes."""

    #: True for a backend that needs the wizard to collect a sudo password
    #: itself (no real controlling tty to prompt on) — see core/executor.py.
    needs_sudo_password = False

    def menu(self, title: str, options: list[str], default: str = "") -> str:
        """Numbered single-choice menu. Returns the raw choice text the
        user picked (e.g. "1", "b") — callers keep their existing parsing."""
        raise NotImplementedError

    def text(self, prompt: str, default: str = "") -> str:
        """Free-text/numeric entry (paths, targets, timing values)."""
        raise NotImplementedError

    def multiselect(self, title: str, items: list[dict]) -> str:
        """Pick zero or more of `items` (each carries whatever display
        fields the caller has — port/service/tool/name/priority, or just
        tool/name). Returns the raw picks string (e.g. "1,3", "r", "a",
        "0") — callers keep their existing parsing, unchanged."""
        raise NotImplementedError

    def confirm(self, cmd: str, impact: str, title: str = "Confirm") -> bool:
        """The safety-critical "show impact, get an explicit yes" gate."""
        raise NotImplementedError

    def status(self, kind: str, text: str, data: dict | None = None) -> None:
        """One-way notification (scan results, credentials found, step
        results) — no reply expected."""
        raise NotImplementedError

    def sudo_password(self) -> str:
        """Only called when `needs_sudo_password` is True."""
        raise NotImplementedError


def _prio_tag(priority: int) -> str:
    if priority >= 4:
        return green("(recommended)")
    if priority == 3:
        return cyan("(optional)   ")
    return "(info)       "


class CliUI(UI):
    """Reproduces the original terminal prompts/menus exactly."""

    needs_sudo_password = False

    def menu(self, title: str, options: list[str], default: str = "") -> str:
        print(f"  {title}")
        for opt in options:
            print(f"    {opt}")
        hint = f" [{default}]" if default else ""
        raw = input(f"  {cyan(f'Choice{hint}: ')}").strip()
        return raw or default

    def text(self, prompt: str, default: str = "") -> str:
        hint = f" [{default}]" if default else ""
        raw = input(f"  {cyan(prompt)}{hint}: ").strip()
        return raw or default

    def multiselect(self, title: str, items: list[dict]) -> str:
        section(title)
        for i, item in enumerate(items, 1):
            port, service = item.get("port"), item.get("service")
            tool, name = item.get("tool", ""), item.get("name", "")
            if port is not None:
                tag = _prio_tag(item.get("priority", 3))
                print(f"    {green(str(i).rjust(2))}. {tag}  "
                      f"{bold(str(port))}/{cyan(service)}  [{tool}] {name}")
            else:
                rec = (green("[recommended]") if item.get("is_recommended")
                       else yellow("[alternative]"))
                print(f"    {green(str(i))}. {magenta(f'[{tool}]')} {name} {rec}")
        print()
        info("(recommended) = leads to creds / shell (top = highest impact).")
        prompt = "Select: numbers (e.g. 1,3,5) / 'r' recommended / 'a' all / '0' none: "
        return input(f"  {cyan(prompt)}").strip()

    def confirm(self, cmd: str, impact: str, title: str = "Confirm") -> bool:
        print(f"\n  {'─' * 60}")
        print(f"  {bold(title)}")
        print(f"  $ {cmd}")
        inner = _width()
        top = "┌─ IMPACT " + "─" * max(0, inner - 9)
        bottom = "└" + "─" * inner
        print(f"  {yellow(top)}")
        for line in textwrap.wrap(impact, inner - 2) or [""]:
            print(f"  {yellow('│')} {line}")
        print(f"  {yellow(bottom)}")
        reply = input(f"  {cyan('Accept impact and proceed? (type yes to run) ')}").strip().lower()
        return reply == "yes"

    def status(self, kind: str, text: str, data: dict | None = None) -> None:
        # The existing `core.display` calls at each status call site already
        # print human-readable text in CLI mode — nothing further needed.
        pass

    def sudo_password(self) -> str:  # pragma: no cover - never called (needs_sudo_password=False)
        return getpass.getpass("  [sudo] password: ")


class IpcUI(UI):
    """JSON-lines protocol over real stdin/stdout for the GUI driver
    (`src/core/wizard_driver.py`) to consume."""

    needs_sudo_password = True

    def __init__(self, stdin=None, stdout=None):
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout

    def _send_recv(self, message: dict) -> dict:
        self._stdout.write(json.dumps(message) + "\n")
        self._stdout.flush()
        line = self._stdin.readline()
        if not line:
            return {}
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {}

    def menu(self, title: str, options: list[str], default: str = "") -> str:
        resp = self._send_recv({
            "type": "menu", "title": title, "options": options, "default": default,
        })
        return str(resp.get("reply", default))

    def text(self, prompt: str, default: str = "") -> str:
        resp = self._send_recv({"type": "text", "prompt": prompt, "default": default})
        return str(resp.get("reply", default))

    def multiselect(self, title: str, items: list[dict]) -> str:
        resp = self._send_recv({"type": "multiselect", "title": title, "items": items})
        return str(resp.get("reply", ""))

    def confirm(self, cmd: str, impact: str, title: str = "Confirm") -> bool:
        resp = self._send_recv({"type": "confirm", "title": title, "cmd": cmd, "impact": impact})
        return bool(resp.get("reply", False))

    def status(self, kind: str, text: str, data: dict | None = None) -> None:
        self._stdout.write(json.dumps({
            "type": "status", "kind": kind, "text": text, "data": data or {},
        }) + "\n")
        self._stdout.flush()

    def sudo_password(self) -> str:
        resp = self._send_recv({"type": "sudo_password"})
        return str(resp.get("reply", ""))


_ui: UI = CliUI()


def set_ui(ui: UI) -> None:
    global _ui
    _ui = ui


def get_ui() -> UI:
    return _ui
