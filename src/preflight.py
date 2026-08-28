"""
Dependency doctor — verifies everything the app needs to actually run its
tool chain, on whatever machine just cloned the repo.

The app is split across two Python runtimes and two OSes:
  * the GUI runs in a Windows Python (PySide6 + a ConPTY/WebEngine terminal),
  * the `chain_wizard` CLI runs inside WSL under the distro's own `python3`
    (a different interpreter entirely).
  * the 6 tools themselves (nmap/masscan/hydra/ncrack/ncat/evil-winrm) run
    sandboxed inside the `therecon-tools` Docker container (docker/), not
    on the WSL host directly — see docs/List การเเก้ไข.md item 5.

"works on my machine" breaks across clones for boring, specific reasons:
missing WSL, a `python3` too old for the CLI's `str | None` syntax, a
Windows `python` that's really the Microsoft Store stub, or Docker not
running / the tool container not built yet. This module checks each of
those explicitly and, for every failure, prints the exact command that
fixes it — instead of letting the first broken CLI invocation fail
cryptically mid-scan.

Pure standard library, never raises (every probe is best-effort with a
timeout), so it is safe to call at GUI startup AND to run standalone:

    python -m src.preflight          # from the repo root, either OS

Exit code is the number of problems found (0 = all good), so installers /
CI can gate on it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

# Name docker/run.sh gives the long-lived tool container.
_TOOL_CONTAINER = "therecon-tools"

# chain_wizard uses PEP 604 unions (`str | None`), so the WSL/native python3
# that runs it must be at least this new. Ubuntu 22.04+ (3.10), Debian 12
# (3.11) and current Kali all satisfy it; only genuinely old distros don't.
_MIN_WIZARD_PY = (3, 10)

# Pseudo-distros `wsl -l` lists that aren't a real Linux userspace to run
# tools in — same set terminal_tabs._wsl_available() filters out.
_WSL_PSEUDO_DISTROS = {"docker-desktop", "docker-desktop-data"}

_WSL_TIMEOUT = 20  # WSL's first call of a session can pay the VM's cold boot.


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    fix: str = ""  # exact command / action to resolve it when not ok


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", fix: str = "") -> None:
        self.checks.append(Check(name, ok, detail, fix))

    @property
    def problems(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    @property
    def ok(self) -> bool:
        return not self.problems


def _run(argv: list[str], timeout: int = _WSL_TIMEOUT) -> tuple[int, str]:
    """Best-effort subprocess: returns (exit_code, combined_output). Never
    raises — a missing binary / timeout becomes a non-zero code so callers
    can treat it as a plain failed check."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            **_NO_WINDOW,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except Exception as exc:  # noqa: BLE001 — doctor must never crash the app
        return 1, str(exc)


# CREATE_NO_WINDOW keeps the WSL probes from flashing console windows when
# the GUI (a windowed process) spawns them. No-op / absent off Windows.
_NO_WINDOW = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}  # type: ignore[attr-defined]
    if os.name == "nt"
    else {}
)


def _wsl_distros() -> list[str]:
    """Real (non-pseudo) WSL distros registered on this machine, or []."""
    if not shutil.which("wsl.exe"):
        return []
    code, out = _run(["wsl.exe", "-l", "-q"], timeout=10)
    if code != 0:
        return []
    # wsl.exe emits UTF-16LE with stray NULs even through a pipe.
    names = {line.replace("\x00", "").strip() for line in out.splitlines()}
    return sorted(n for n in names if n and n not in _WSL_PSEUDO_DISTROS)


def _check_gui_python(rep: Report) -> None:
    """The interpreter running THIS process — i.e. the one the GUI uses.
    A Microsoft Store `python` stub reports a version but can't build a
    venv or import compiled wheels; flag anything below 3.9 (PySide6's
    floor) as the actionable signal."""
    v = sys.version_info
    ok = v[:2] >= (3, 9)
    rep.add(
        "GUI Python",
        ok,
        detail=f"{v.major}.{v.minor}.{v.micro} ({sys.executable})",
        fix="" if ok else "Install Python 3.10+ from python.org (not the "
        "Microsoft Store stub) and recreate the venv.",
    )


def _check_import(rep: Report, name: str, module: str, fix: str) -> None:
    try:
        __import__(module)
        rep.add(name, True, detail="importable")
    except Exception as exc:  # noqa: BLE001
        rep.add(name, False, detail=str(exc), fix=fix)


def _check_windows_stack(rep: Report) -> None:
    _reqs = ".venv\\Scripts\\pip install -r requirements.txt"
    _check_import(rep, "PySide6", "PySide6", _reqs)
    _check_import(
        rep, "QtWebEngine (terminal)", "PySide6.QtWebEngineWidgets",
        "Reinstall PySide6-Addons: " + _reqs,
    )
    _check_import(rep, "pywinpty (ConPTY)", "winpty", _reqs)

    distros = _wsl_distros()
    if not shutil.which("wsl.exe"):
        rep.add(
            "WSL", False, detail="wsl.exe not on PATH",
            fix="Run in an elevated PowerShell: wsl --install  (needs a reboot)",
        )
        return
    rep.add("WSL", True, detail="wsl.exe present")
    if not distros:
        rep.add(
            "WSL distro", False, detail="no real distro registered",
            fix="wsl --install -d Ubuntu  (reboot, then open Ubuntu once)",
        )
        return
    rep.add("WSL distro", True, detail=", ".join(distros))
    _check_wsl_python(rep, prefix=["wsl.exe", "-e", "bash", "-lc"])
    _check_docker(rep, prefix=["wsl.exe", "-e", "bash", "-lc"])


def _check_linux_stack(rep: Report) -> None:
    _check_import(
        rep, "PySide6", "PySide6",
        ".venv/bin/pip install -r requirements.txt",
    )
    _check_wsl_python(rep, prefix=["bash", "-lc"])
    _check_docker(rep, prefix=["bash", "-lc"])


def _check_wsl_python(rep: Report, prefix: list[str]) -> None:
    """The python3 that will actually run `chain_wizard` — separate from the
    GUI's interpreter when on Windows (it lives inside WSL)."""
    code, out = _run(prefix + [
        'python3 -c "import sys;print(\\"%d.%d.%d\\" % sys.version_info[:3])"'
    ])
    label = "Tool-runner python3"
    if code != 0:
        rep.add(
            label, False, detail=out.strip() or "python3 not found",
            fix="Inside the distro: sudo apt-get install -y python3",
        )
        return
    ver = out.strip().splitlines()[-1].strip() if out.strip() else ""
    try:
        parts = tuple(int(x) for x in ver.split("."))
        ok = parts[:2] >= _MIN_WIZARD_PY
    except Exception:  # noqa: BLE001
        ok, parts = False, ()
    rep.add(
        label, ok, detail=ver or "unknown",
        fix="" if ok else
        f"chain_wizard needs python3 >= {_MIN_WIZARD_PY[0]}.{_MIN_WIZARD_PY[1]}; "
        "use a newer distro (Ubuntu 22.04+/Debian 12/Kali).",
    )


def _check_docker(rep: Report, prefix: list[str]) -> None:
    """The 6 tools live in the `therecon-tools` container (docker/), not
    on the WSL host — check Docker itself is reachable and that container
    is actually running, instead of probing for the tools on $PATH (they
    were deliberately removed from the host, see docs/List การเเก้ไข.md
    item 5)."""
    code, out = _run(prefix + ["docker version --format '{{.Server.Version}}'"])
    if code != 0:
        rep.add(
            "Docker", False, detail=out.strip() or "docker not reachable",
            fix="Inside the WSL distro: sudo systemctl enable --now docker "
            "(installed via: sudo apt-get install -y docker.io)",
        )
        return
    rep.add("Docker", True, detail=f"server {out.strip()}")

    code, out = _run(prefix + [
        f"docker inspect -f '{{{{.State.Running}}}}' {_TOOL_CONTAINER}"
    ])
    running = code == 0 and out.strip() == "true"
    rep.add(
        f"container: {_TOOL_CONTAINER}", running,
        detail="running" if running else (out.strip() or "not found"),
        fix="" if running else "From the repo root (inside WSL): ./docker/run.sh",
    )


def run_checks() -> Report:
    """Full doctor pass for the current machine. Never raises."""
    rep = Report()
    _check_gui_python(rep)
    if os.name == "nt":
        _check_windows_stack(rep)
    else:
        _check_linux_stack(rep)
    return rep


def format_text(rep: Report) -> str:
    """Plain-text report for the CLI / logs."""
    lines = ["TheRecon preflight", "=" * 40]
    for c in rep.checks:
        mark = "OK  " if c.ok else "FAIL"
        lines.append(f"[{mark}] {c.name}: {c.detail}")
        if not c.ok and c.fix:
            lines.append(f"        fix: {c.fix}")
    lines.append("=" * 40)
    lines.append(
        "all checks passed" if rep.ok
        else f"{len(rep.problems)} problem(s) found — see fixes above"
    )
    return "\n".join(lines)


def format_problems_html(rep: Report) -> str:
    """Compact HTML body listing only the failures + fixes — for the
    startup warning dialog. Empty string when everything passed."""
    if rep.ok:
        return ""
    rows = ["<p>Some tools this app needs aren't ready yet. It will still "
            "open, but scans using the missing pieces will fail until you "
            "fix them:</p><ul>"]
    for c in rep.problems:
        fix = f"<br><code>{c.fix}</code>" if c.fix else ""
        rows.append(f"<li><b>{c.name}</b> — {c.detail}{fix}</li>")
    rows.append("</ul>")
    return "".join(rows)


def main() -> int:
    rep = run_checks()
    print(format_text(rep))
    return len(rep.problems)


if __name__ == "__main__":
    raise SystemExit(main())
