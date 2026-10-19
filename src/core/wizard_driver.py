"""
Wizard Driver — the Qt-side half of the JSON IPC protocol
`chain_wizard/core/ui_driver.py::IpcUI` speaks.

Owns the `chain_wizard` subprocess (`python3 -m wizard.main --gui ...`,
launched over plain pipes — never a PTY/xterm, so nothing is ever rendered
as a terminal) and the safety semantics: every `confirm` request routes
through a `ConfirmationGate(channel="wizard")`, so the wizard's audit trail
lands in the same `logs/audit_log.jsonl` as Direct Tool Mode / LLM Mode
instead of a second bespoke log. This module holds no widget code — the
dialogs that answer each signal live in `src/ui/wizard_dialogs.py`.

Command building stays entirely inside `chain_wizard/` (per CLAUDE.md's
"GUI never builds commands or holds security logic"): every `cmd`/`impact`
string this module hands to a signal was already built there — this module
and its dialogs only render it and return a choice/boolean.
"""

from __future__ import annotations

import json
import os
import shlex

from PySide6.QtCore import QObject, QProcess, Signal

from src.core.confirmation_gate import ConfirmationGate
from src.ui.terminal_launch import _repo_local_dir, _wsl_dir


class WizardDriver(QObject):
    """One instance per wizard run. Usage:

        driver = WizardDriver(target=..., user_wl=..., pass_wl=...)
        driver.menuRequested.connect(...)
        driver.textRequested.connect(...)
        driver.multiselectRequested.connect(...)
        driver.confirmRequested.connect(...)      # dict has "preview_box"
        driver.sudoPasswordRequested.connect(...)
        driver.statusUpdate.connect(...)
        driver.finished.connect(...)
        driver.start()
        # ... later, from a dialog's callback ...
        driver.respond({"reply": ...})
    """

    menuRequested = Signal(dict)
    textRequested = Signal(dict)
    multiselectRequested = Signal(dict)
    confirmRequested = Signal(dict)
    sudoPasswordRequested = Signal()
    statusUpdate = Signal(dict)
    rawOutput = Signal(str)  # subprocess stderr — the wizard's real print() text
    finished = Signal(int)  # exit code
    errorOccurred = Signal(str)

    def __init__(self, target: str, user_wordlist: str,
                 pass_wordlist: str, parent: QObject | None = None):
        super().__init__(parent)
        self._target = target
        self._user_wl = user_wordlist
        self._pass_wl = pass_wordlist
        self._gate = ConfirmationGate(channel="wizard")
        self._buf = b""
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.readyReadStandardError.connect(self._on_stderr)
        self._proc.finished.connect(lambda code, _status: self.finished.emit(code))
        self._proc.errorOccurred.connect(
            lambda _err: self.errorOccurred.emit(self._proc.errorString()))

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        args = ["--target", self._target, "--gui"]
        if self._user_wl:
            args += ["--user-wordlist", self._user_wl]
        if self._pass_wl:
            args += ["--pass-wordlist", self._pass_wl]

        if os.name == "nt":
            wsl_dir = _wsl_dir()
            script = f"cd '{wsl_dir}' && exec python3 -m wizard.main " + \
                     " ".join(shlex.quote(a) for a in args)
            self._proc.start("wsl.exe", ["-e", "bash", "-lc", script])
        else:
            self._proc.setWorkingDirectory(_repo_local_dir())
            self._proc.start("python3", ["-m", "wizard.main", *args])

    def stop(self) -> None:
        if self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()

    # -- protocol -------------------------------------------------------

    def respond(self, reply_message: dict) -> None:
        """Write one JSON line back to the subprocess's stdin — the answer
        to whichever `*Requested`/`sudoPasswordRequested` signal is
        currently pending."""
        line = json.dumps(reply_message) + "\n"
        self._proc.write(line.encode("utf-8"))

    def respond_confirm(self, accepted: bool) -> None:
        """Answer a `confirmRequested` — routes the yes/no through the same
        `ConfirmationGate.confirm()` exact-match + audit-log path every
        other execution surface in the app uses."""
        if accepted:
            self._gate.confirm("yes")
        else:
            self._gate.cancel("user_declined")
        self.respond({"reply": accepted})

    def _on_stderr(self) -> None:
        """The wizard's `core.display` calls (section/info/ok/warn, and every
        step's captured command output echoed via `_echo_output`) are plain
        `print()`s redirected to stderr in `--gui` mode so they never
        corrupt the stdout JSON stream (see `wizard/main.py`). Surface that
        text as-is — it's real captured output, not typed into a shell."""
        chunk = bytes(self._proc.readAllStandardError()).decode(
            "utf-8", errors="replace")
        if chunk:
            self.rawOutput.emit(chunk)

    def _on_stdout(self) -> None:
        self._buf += bytes(self._proc.readAllStandardOutput())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                message = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            self._dispatch(message)

    def _dispatch(self, message: dict) -> None:
        kind = message.get("type")
        if kind == "menu":
            self.menuRequested.emit(message)
        elif kind == "text":
            self.textRequested.emit(message)
        elif kind == "multiselect":
            self.multiselectRequested.emit(message)
        elif kind == "confirm":
            result = self._gate.request(
                message.get("cmd", ""), self._target,
                extra_impact=message.get("impact"), skip_scope=True,
            )
            payload = dict(message)
            payload["preview_box"] = result.preview_box or message.get("impact", "")
            payload["allowed"] = result.ok
            payload["reject_reason"] = None if result.ok else result.message
            self.confirmRequested.emit(payload)
        elif kind == "sudo_password":
            self.sudoPasswordRequested.emit()
        elif kind == "status":
            self.statusUpdate.emit(message)
